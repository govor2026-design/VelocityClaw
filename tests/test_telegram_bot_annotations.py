from typing import get_type_hints

from velocity_claw.telegram_bot.bot import VelocityClawTelegramBot


def test_telegram_bot_initializer_declares_none_return() -> None:
    hints = get_type_hints(VelocityClawTelegramBot.__init__)

    assert hints["return"] is type(None)


def test_handler_registration_declares_none_return() -> None:
    hints = get_type_hints(VelocityClawTelegramBot._register_handlers)

    assert hints["return"] is type(None)


def test_polling_entrypoint_declares_none_return() -> None:
    hints = get_type_hints(VelocityClawTelegramBot.run)

    assert hints["return"] is type(None)


def test_report_mapping_annotation_is_parameterized() -> None:
    hints = get_type_hints(VelocityClawTelegramBot._format_report)

    assert hints["report"] == dict[str, object]


def test_reply_helper_declares_return_type() -> None:
    hints = get_type_hints(VelocityClawTelegramBot._reply)

    assert hints["return"] is object


def test_start_handler_declares_optional_reply_return() -> None:
    hints = get_type_hints(VelocityClawTelegramBot.start)

    assert hints["return"] == object | None


def test_help_handler_declares_optional_reply_return() -> None:
    hints = get_type_hints(VelocityClawTelegramBot.help)

    assert hints["return"] == object | None


def test_status_handler_declares_optional_reply_return() -> None:
    hints = get_type_hints(VelocityClawTelegramBot.status)

    assert hints["return"] == object | None


def test_model_handler_declares_optional_reply_return() -> None:
    hints = get_type_hints(VelocityClawTelegramBot.model)

    assert hints["return"] == object | None


def test_reset_handler_declares_optional_reply_return() -> None:
    hints = get_type_hints(VelocityClawTelegramBot.reset)

    assert hints["return"] == object | None
