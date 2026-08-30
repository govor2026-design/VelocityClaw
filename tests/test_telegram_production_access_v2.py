from unittest.mock import patch

import pytest

from velocity_claw.config.settings import Settings, SettingsValidationError


def test_production_rejects_telegram_token_without_allowed_chat() -> None:
    env = {
        "ENV": "production",
        "TELEGRAM_TOKEN": "123456:secret",
        "TELEGRAM_CHAT_ID": "",
    }

    with (
        patch.dict("os.environ", env, clear=True),
        pytest.raises(SettingsValidationError, match="TELEGRAM_CHAT_ID must be set"),
    ):
        Settings()


def test_production_accepts_telegram_token_with_allowed_chat() -> None:
    env = {
        "ENV": "production",
        "TELEGRAM_TOKEN": "123456:secret",
        "TELEGRAM_CHAT_ID": "-1001234567890",
    }

    with patch.dict("os.environ", env, clear=True):
        settings = Settings()

    assert settings.telegram_chat_id == "-1001234567890"


def test_prefixed_production_config_enforces_allowed_chat() -> None:
    env = {
        "VELOCITY_CLAW_ENV": "production",
        "VELOCITY_CLAW_TELEGRAM_TOKEN": "123456:secret",
    }

    with (
        patch.dict("os.environ", env, clear=True),
        pytest.raises(SettingsValidationError, match="TELEGRAM_CHAT_ID must be set"),
    ):
        Settings()


def test_non_production_can_bootstrap_telegram_without_chat_restriction() -> None:
    env = {
        "ENV": "development",
        "TELEGRAM_TOKEN": "123456:secret",
        "TELEGRAM_CHAT_ID": "",
    }

    with patch.dict("os.environ", env, clear=True):
        settings = Settings()

    assert settings.telegram_chat_id == ""
