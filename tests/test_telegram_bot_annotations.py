from typing import get_type_hints

from velocity_claw.telegram_bot.bot import VelocityClawTelegramBot


def test_telegram_bot_initializer_declares_none_return() -> None:
    hints = get_type_hints(VelocityClawTelegramBot.__init__)

    assert hints["return"] is type(None)


def test_handler_registration_declares_none_return() -> None:
    hints = get_type_hints(VelocityClawTelegramBot._register_handlers)

    assert hints["return"] is type(None)
