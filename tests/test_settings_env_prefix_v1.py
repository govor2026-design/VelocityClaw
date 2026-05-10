from unittest.mock import patch

from velocity_claw.config.settings import Settings


def test_settings_default_to_safe_shell_and_git_disabled():
    with patch.dict("os.environ", {}, clear=True):
        settings = Settings()

    assert settings.shell_enabled is False
    assert settings.git_enabled is False


def test_prefixed_deployment_env_values_are_honored():
    env = {
        "VELOCITY_CLAW_ENV": "production",
        "VELOCITY_CLAW_SAFE_MODE": "true",
        "VELOCITY_CLAW_SHELL_ENABLED": "false",
        "VELOCITY_CLAW_GIT_ENABLED": "false",
        "VELOCITY_CLAW_API_PORT": "9012",
        "VELOCITY_CLAW_WORKSPACE_ROOT": "/srv/velocity-claw/workspace",
        "VELOCITY_CLAW_MEMORY_DB_PATH": "/var/lib/velocity-claw/memory.db",
        "VELOCITY_CLAW_EXECUTION_PROFILE": "safe",
    }
    with patch.dict("os.environ", env, clear=True):
        settings = Settings()

    assert settings.env == "production"
    assert settings.safe_mode is True
    assert settings.shell_enabled is False
    assert settings.git_enabled is False
    assert settings.api_port == 9012
    assert settings.workspace_root == "/srv/velocity-claw/workspace"
    assert settings.memory_db_path == "/var/lib/velocity-claw/memory.db"
    assert settings.execution_profile == "safe"


def test_prefixed_env_values_override_legacy_values():
    env = {
        "API_PORT": "8000",
        "VELOCITY_CLAW_API_PORT": "9000",
        "SHELL_ENABLED": "true",
        "VELOCITY_CLAW_SHELL_ENABLED": "false",
        "GIT_ENABLED": "true",
        "VELOCITY_CLAW_GIT_ENABLED": "false",
    }
    with patch.dict("os.environ", env, clear=True):
        settings = Settings()

    assert settings.api_port == 9000
    assert settings.shell_enabled is False
    assert settings.git_enabled is False


def test_legacy_env_values_still_work_for_local_dotenv_files():
    env = {
        "API_PORT": "8123",
        "SHELL_ENABLED": "true",
        "GIT_ENABLED": "true",
    }
    with patch.dict("os.environ", env, clear=True):
        settings = Settings()

    assert settings.api_port == 8123
    assert settings.shell_enabled is True
    assert settings.git_enabled is True
