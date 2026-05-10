from __future__ import annotations

import secrets
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from velocity_claw.logs.logger import get_logger

LOGGER = get_logger("velocity_claw.api.errors")
REQUEST_ID_HEADER = "X-Request-ID"
API_KEY_HEADER = "X-API-Key"
PUBLIC_PATHS = {"/health", "/docs", "/redoc", "/openapi.json"}


def error_payload(*, code: str, message: str, request_id: str | None = None, details: Any = None) -> dict:
    payload = {
        "status": "error",
        "error": {
            "code": code,
            "message": message,
        },
    }
    if request_id:
        payload["request_id"] = request_id
    if details is not None:
        payload["error"]["details"] = details
    return payload


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


class ApiKeyAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        settings = getattr(request.app.state, "settings", None)
        expected_key = getattr(settings, "api_key", None)
        if not expected_key or request.url.path in PUBLIC_PATHS:
            return await call_next(request)
        supplied_key = request.headers.get(API_KEY_HEADER)
        authorization = request.headers.get("Authorization", "")
        if authorization.startswith("Bearer "):
            supplied_key = authorization.removeprefix("Bearer ").strip()
        if supplied_key and secrets.compare_digest(str(supplied_key), str(expected_key)):
            return await call_next(request)
        request_id = get_request_id(request)
        LOGGER.warning("Unauthorized API request request_id=%s path=%s", request_id, request.url.path)
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content=error_payload(code="unauthorized", message="Valid API key required", request_id=request_id),
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    request_id = get_request_id(request)
    detail = exc.detail
    if isinstance(detail, dict):
        code = str(detail.get("error") or detail.get("code") or "http_error")
        message = str(detail.get("detail") or detail.get("message") or "HTTP error")
        details = detail if detail else None
    else:
        code = "http_error"
        message = str(detail or "HTTP error")
        details = None
    LOGGER.warning("HTTP error request_id=%s status=%s code=%s message=%s", request_id, exc.status_code, code, message)
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(code=code, message=message, request_id=request_id, details=details),
        headers=exc.headers,
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    request_id = get_request_id(request)
    LOGGER.warning("Validation error request_id=%s errors=%s", request_id, exc.errors())
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_payload(
            code="validation_error",
            message="Request validation failed",
            request_id=request_id,
            details=exc.errors(),
        ),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = get_request_id(request)
    LOGGER.exception("Unhandled API exception request_id=%s", request_id)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_payload(
            code="internal_error",
            message="Internal server error",
            request_id=request_id,
        ),
    )


def install_api_error_handlers(app: FastAPI) -> FastAPI:
    app.add_middleware(ApiKeyAuthMiddleware)
    app.add_middleware(RequestIdMiddleware)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
    return app
