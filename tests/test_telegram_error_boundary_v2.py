import asyncio
import sys
from types import ModuleType, SimpleNamespace
from typing import get_type_hints
from unittest.mock import AsyncMock, Mock, call, patch

from velocity_claw.telegram_bot.bot import VelocityClawTelegramBot


class _Filter:
    def __or__(self, _other):
        return self

    def __and__(self, _other):
        return self

    def __invert__(self):
        return self


def test_telegram_registers_global_error_handler() -> None:
    telegram_module = ModuleType("telegram")
    telegram_ext = ModuleType("telegram.ext")
    telegram_ext.CommandHandler = lambda *args: args
    telegram_ext.MessageHandler = lambda *args: args
    telegram_ext.filters = SimpleNamespace(
        Document=SimpleNamespace(ALL=_Filter()),
        TEXT=_Filter(),
        COMMAND=_Filter(),
    )
    bot = object.__new__(VelocityClawTelegramBot)
    bot.app = SimpleNamespace(add_handler=Mock(), add_error_handler=Mock())

    with patch.dict(sys.modules, {"telegram": telegram_module, "telegram.ext": telegram_ext}):
        bot._register_handlers()

    bot.app.add_error_handler.assert_called_once_with(bot._handle_error)


def test_telegram_error_handler_declares_none_return() -> None:
    hints = get_type_hints(VelocityClawTelegramBot._handle_error)

    assert hints["return"] is type(None)


def test_telegram_error_handler_logs_traceback_and_returns_safe_reply() -> None:
    secret = "provider-token-secret"
    error = RuntimeError(secret)
    bot = object.__new__(VelocityClawTelegramBot)
    bot.settings = SimpleNamespace(telegram_chat_id="123")
    bot.logger = Mock()
    bot._reply = AsyncMock()
    update = SimpleNamespace(effective_chat=SimpleNamespace(id=123), message=object())
    context = SimpleNamespace(error=error)

    asyncio.run(bot._handle_error(update, context))

    bot.logger.error.assert_called_once_with(
        "Unhandled Telegram update error",
        exc_info=(RuntimeError, error, error.__traceback__),
    )
    bot._reply.assert_awaited_once()
    reply_text = bot._reply.await_args.args[1]
    assert reply_text == "Не удалось обработать запрос. Попробуйте ещё раз."
    assert secret not in reply_text


def test_telegram_error_handler_does_not_reply_to_unauthorized_chat() -> None:
    bot = object.__new__(VelocityClawTelegramBot)
    bot.settings = SimpleNamespace(telegram_chat_id="123")
    bot.logger = Mock()
    bot._reply = AsyncMock()
    update = SimpleNamespace(effective_chat=SimpleNamespace(id=456), message=object())

    asyncio.run(bot._handle_error(update, SimpleNamespace(error=RuntimeError("failure"))))

    bot._reply.assert_not_awaited()


def test_telegram_error_handler_does_not_reply_without_effective_chat() -> None:
    bot = object.__new__(VelocityClawTelegramBot)
    bot.settings = SimpleNamespace(telegram_chat_id="123")
    bot.logger = Mock()
    bot._reply = AsyncMock()
    update = SimpleNamespace(effective_chat=None, message=object())

    asyncio.run(bot._handle_error(update, SimpleNamespace(error=RuntimeError("failure"))))

    bot._reply.assert_not_awaited()


def test_telegram_error_handler_contains_reply_failures() -> None:
    bot = object.__new__(VelocityClawTelegramBot)
    bot.settings = SimpleNamespace(telegram_chat_id=None)
    bot.logger = Mock()
    bot._reply = AsyncMock(side_effect=RuntimeError("telegram unavailable"))
    update = SimpleNamespace(effective_chat=SimpleNamespace(id=123), message=object())
    task_error = RuntimeError("task failure")

    asyncio.run(bot._handle_error(update, SimpleNamespace(error=task_error)))

    assert bot.logger.mock_calls == [
        call.error(
            "Unhandled Telegram update error",
            exc_info=(RuntimeError, task_error, None),
        ),
        call.exception("Failed to send Telegram error response"),
    ]
