from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from velocity_claw.api.app import app as uvicorn_app
from velocity_claw.api.app import create_app
from velocity_claw.api.errors import REQUEST_ID_HEADER
from velocity_claw.config.settings import Settings


def test_hardened_app_factory_installs_error_handlers():
    app = create_app()
    assert app.state.api_error_handlers_installed is True


def test_module_exposes_default_uvicorn_app():
    assert uvicorn_app.state.api_error_handlers_installed is True


def test_hardened_app_adds_request_id_header_on_real_health_endpoint():
    client = TestClient(create_app(), raise_server_exceptions=False)
    response = client.get("/health", headers={REQUEST_ID_HEADER: "real-api-request-1"})
    assert response.status_code == 200
    assert response.headers[REQUEST_ID_HEADER] == "real-api-request-1"


def test_cli_uses_hardened_api_app_factory():
    content = Path("velocity_claw/cli.py").read_text(encoding="utf-8")
    assert "from velocity_claw.api.app import create_app" in content
    assert "from velocity_claw.api.server import create_app" not in content


def test_task_internal_error_is_redacted(tmp_path, monkeypatch):
    secret = "provider-token=secret-value"
    settings = Settings(
        workspace_root=str(tmp_path),
        memory_db_path=str(tmp_path / "memory.db"),
    )
    monkeypatch.setenv("VELOCITY_CLAW_API_KEY", "test-key")
    with patch("velocity_claw.api.server.load_settings", return_value=settings):
        app = create_app()
    app.state.agent.run_task = AsyncMock(side_effect=RuntimeError(secret))

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/task",
            json={"task": "trigger failure"},
            headers={"X-API-Key": "test-key"},
        )

    assert response.status_code == 500
    assert secret not in response.text
    payload = response.json()
    assert payload["error"]["code"] == "internal_error"
    assert payload["error"]["message"] == "Internal server error"
    assert payload["error"]["details"]["detail"] == "Internal server error"
