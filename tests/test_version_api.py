from fastapi import FastAPI
from fastapi.testclient import TestClient

from velocity_claw.api.app import install_version_endpoint
from velocity_claw.api.version import build_version_payload
from velocity_claw.__version__ import __product_name__, __release_stage__, __version__


class FakeSettings:
    env = "production"
    execution_profile = "safe"
    safe_mode = True
    trusted_mode = False


def test_build_version_payload_uses_package_metadata_and_runtime_settings():
    payload = build_version_payload(FakeSettings())

    assert payload["status"] == "ok"
    assert payload["product"] == __product_name__
    assert payload["version"] == __version__
    assert payload["release_stage"] == __release_stage__
    assert payload["runtime"]["env"] == "production"
    assert payload["runtime"]["execution_profile"] == "safe"
    assert payload["runtime"]["safe_mode"] is True
    assert payload["runtime"]["trusted_mode"] is False


def test_version_endpoint_returns_version_payload():
    app = FastAPI()
    app.state.settings = FakeSettings()
    install_version_endpoint(app)
    client = TestClient(app)

    response = client.get("/version")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["product"] == __product_name__
    assert payload["version"] == __version__
    assert payload["runtime"]["execution_profile"] == "safe"
