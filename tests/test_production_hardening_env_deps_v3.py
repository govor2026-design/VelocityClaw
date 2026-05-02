import tomllib
from pathlib import Path

import pytest

from velocity_claw.config.settings import Settings, SettingsValidationError, parse_bool, parse_int


def test_requirements_are_pinned_for_reproducible_installs():
    lines = [line.strip() for line in Path("requirements.txt").read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")]
    assert lines
    assert all("==" in line for line in lines)


def test_pyproject_runtime_dependencies_are_pinned():
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    dependencies = pyproject["project"]["dependencies"]
    dev_dependencies = pyproject["project"]["optional-dependencies"]["dev"]
    assert dependencies
    assert all("==" in item for item in dependencies)
    assert all("==" in item for item in dev_dependencies)


def test_settings_reject_invalid_bool_and_int():
    with pytest.raises(SettingsValidationError):
        parse_bool("maybe")
    with pytest.raises(SettingsValidationError):
        parse_int("API_PORT", "not-a-port", 8000)
    with pytest.raises(SettingsValidationError):
        parse_int("API_PORT", "70000", 8000, min_value=1, max_value=65535)


def test_settings_reject_invalid_environment(monkeypatch):
    monkeypatch.setenv("ENV", "broken")
    with pytest.raises(SettingsValidationError, match="ENV must be"):
        Settings()


def test_settings_reject_owner_profile_without_allowed_users_in_production(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("EXECUTION_PROFILE", "owner")
    monkeypatch.setenv("ALLOWED_USERS", "")
    with pytest.raises(SettingsValidationError, match="ALLOWED_USERS"):
        Settings()


def test_settings_accept_valid_hardened_defaults(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("TRUSTED_MODE", "false")
    monkeypatch.setenv("EXECUTION_PROFILE", "safe")
    monkeypatch.setenv("API_PORT", "8000")
    settings = Settings()
    assert settings.env == "production"
    assert settings.api_port == 8000
    assert settings.execution_profile == "safe"
