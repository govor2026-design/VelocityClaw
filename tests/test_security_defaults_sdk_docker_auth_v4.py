from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from velocity_claw.api.app import create_app
from velocity_claw.api.errors import API_KEY_HEADER
from velocity_claw.config.settings import Settings


def test_settings_default_shell_and_git_are_disabled(monkeypatch):
    monkeypatch.delenv("SHELL_ENABLED", raising=False)
    monkeypatch.delenv("GIT_ENABLED", raising=False)
    settings = Settings(env="test")
    assert settings.shell_enabled is False
    assert settings.git_enabled is False


def test_env_example_uses_safe_shell_and_git_defaults():
    content = Path(".env.example").read_text(encoding="utf-8")
    assert "SHELL_ENABLED=false" in content
    assert "GIT_ENABLED=false" in content
    assert "API_KEY=" in content


def test_provider_sdks_are_declared_in_requirements_and_pyproject():
    requirements = Path("requirements.txt").read_text(encoding="utf-8")
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    for dependency in ["openai==", "anthropic==", "google-generativeai=="]:
        assert dependency in requirements
        assert dependency in pyproject


def test_dockerfile_installs_without_user_flag_and_has_healthcheck():
    content = Path("Dockerfile").read_text(encoding="utf-8")
    assert "pip install --no-cache-dir -r requirements.txt" in content
    assert "--user" not in content
    assert "curl" in content
    assert "HEALTHCHECK" in content
    assert "http://localhost:8000/health" in content


def test_api_key_auth_protects_non_health_endpoints(tmp_path):
    settings = Settings(env="test", memory_db_path=str(tmp_path / "memory.db"), api_key="secret-token")
    with patch("velocity_claw.api.server.load_settings", return_value=settings):
        app = create_app()
        client = TestClient(app, raise_server_exceptions=False)
        assert client.get("/health").status_code == 200
        unauthorized = client.get("/status")
        assert unauthorized.status_code == 401
        assert unauthorized.json()["error"]["code"] == "unauthorized"
        authorized = client.get("/status", headers={API_KEY_HEADER: "secret-token"})
        assert authorized.status_code == 200
        bearer = client.get("/status", headers={"Authorization": "Bearer secret-token"})
        assert bearer.status_code == 200
