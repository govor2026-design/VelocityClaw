from pathlib import Path

from fastapi.testclient import TestClient

from velocity_claw.api.app import create_app
from velocity_claw.api.errors import REQUEST_ID_HEADER


def test_hardened_app_factory_installs_error_handlers():
    app = create_app()
    assert app.state.api_error_handlers_installed is True


def test_hardened_app_adds_request_id_header_on_real_health_endpoint():
    client = TestClient(create_app(), raise_server_exceptions=False)
    response = client.get("/health", headers={REQUEST_ID_HEADER: "real-api-request-1"})
    assert response.status_code == 200
    assert response.headers[REQUEST_ID_HEADER] == "real-api-request-1"


def test_cli_uses_hardened_api_app_factory():
    content = Path("cli.py").read_text(encoding="utf-8")
    assert "from velocity_claw.api.app import create_app" in content
    assert "from velocity_claw.api.server import create_app" not in content
