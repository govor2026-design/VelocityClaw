import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from velocity_claw.telegram_bot.bot import VelocityClawTelegramBot


def test_stop_command_requests_full_polling_shutdown() -> None:
    bot = object.__new__(VelocityClawTelegramBot)
    bot.settings = SimpleNamespace(telegram_chat_id=None)
    bot._reply = AsyncMock()
    bot.app = SimpleNamespace(stop_running=Mock())
    update = SimpleNamespace(effective_chat=SimpleNamespace(id=123), message=object())

    asyncio.run(bot.stop(update, None))

    bot._reply.assert_awaited_once_with(update, "Velocity Claw остановлен вручную.")
    bot.app.stop_running.assert_called_once_with()


def test_stop_command_does_not_stop_for_unauthorized_chat() -> None:
    bot = object.__new__(VelocityClawTelegramBot)
    bot.settings = SimpleNamespace(telegram_chat_id="123")
    bot._reply = AsyncMock()
    bot.app = SimpleNamespace(stop_running=Mock())
    update = SimpleNamespace(effective_chat=SimpleNamespace(id=456), message=object())

    result = asyncio.run(bot.stop(update, None))

    bot._reply.assert_awaited_once_with(update, "Access denied.")
    bot.app.stop_running.assert_not_called()
    assert result is bot._reply.return_value
