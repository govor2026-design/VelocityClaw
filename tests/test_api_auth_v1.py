import os
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from velocity_claw.api.auth import install_api_key_auth


def make_client():
    app = FastAPI()

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/protected")
    def protected():
        return {"status": "ok"}

    install_api_key_auth(app)
    return TestClient(app)


def test_health_is_public_without_api_key():
    with patch.dict(os.environ, {}, clear=True):
        client = make_client()
        response = client.get("/health")
    assert response.status_code == 200


def test_protected_route_requires_configured_api_key():
    with patch.dict(os.environ, {}, clear=True):
        client = make_client()
        response = client.get("/protected")
    assert response.status_code == 503
    assert response.json()["error"] == "api_key_not_configured"


def test_protected_route_accepts_x_api_key():
    with patch.dict(os.environ, {"API_KEY": "test-key-123"}, clear=True):
        client = make_client()
        response = client.get("/protected", headers={"X-API-Key": "test-key-123"})
    assert response.status_code == 200


def test_protected_route_accepts_bearer_token():
    with patch.dict(os.environ, {"VELOCITY_CLAW_API_KEY": "test-key-456"}, clear=True):
        client = make_client()
        response = client.get("/protected", headers={"Authorization": "Bearer test-key-456"})
    assert response.status_code == 200


def test_protected_route_rejects_wrong_key():
    with patch.dict(os.environ, {"API_KEY": "test-key-123"}, clear=True):
        client = make_client()
        response = client.get("/protected", headers={"X-API-Key": "wrong-key"})
    assert response.status_code == 401
