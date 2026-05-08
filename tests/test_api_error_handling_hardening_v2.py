from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

from velocity_claw.api.errors import REQUEST_ID_HEADER, install_api_error_handlers


class Payload(BaseModel):
    name: str


def build_app():
    app = FastAPI()
    install_api_error_handlers(app)

    @app.get("/ok")
    def ok():
        return {"status": "ok"}

    @app.get("/not-found")
    def not_found():
        raise HTTPException(status_code=404, detail={"error": "not_found", "detail": "Missing"})

    @app.post("/payload")
    def payload(item: Payload):
        return item

    @app.get("/boom")
    def boom():
        raise RuntimeError("secret traceback detail")

    return app


def test_request_id_header_is_added_and_preserved():
    client = TestClient(build_app(), raise_server_exceptions=False)
    response = client.get("/ok", headers={REQUEST_ID_HEADER: "req-test-1"})
    assert response.status_code == 200
    assert response.headers[REQUEST_ID_HEADER] == "req-test-1"


def test_http_exception_uses_consistent_error_shape():
    client = TestClient(build_app(), raise_server_exceptions=False)
    response = client.get("/not-found", headers={REQUEST_ID_HEADER: "req-test-2"})
    assert response.status_code == 404
    payload = response.json()
    assert payload["status"] == "error"
    assert payload["request_id"] == "req-test-2"
    assert payload["error"]["code"] == "not_found"
    assert payload["error"]["message"] == "Missing"


def test_validation_error_uses_consistent_error_shape():
    client = TestClient(build_app(), raise_server_exceptions=False)
    response = client.post("/payload", json={}, headers={REQUEST_ID_HEADER: "req-test-3"})
    assert response.status_code == 422
    payload = response.json()
    assert payload["status"] == "error"
    assert payload["request_id"] == "req-test-3"
    assert payload["error"]["code"] == "validation_error"
    assert "details" in payload["error"]


def test_unhandled_exception_returns_safe_500_without_traceback_leak():
    client = TestClient(build_app(), raise_server_exceptions=False)
    response = client.get("/boom", headers={REQUEST_ID_HEADER: "req-test-4"})
    assert response.status_code == 500
    payload = response.json()
    assert payload["status"] == "error"
    assert payload["request_id"] == "req-test-4"
    assert payload["error"]["code"] == "internal_error"
    assert payload["error"]["message"] == "Internal server error"
    assert "secret traceback detail" not in response.text
