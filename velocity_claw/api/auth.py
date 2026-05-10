from __future__ import annotations

import os
from hmac import compare_digest
from typing import Iterable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

PUBLIC_PATHS = {"/health"}


def _env_api_key() -> str | None:
    value = os.getenv("VELOCITY_CLAW_API_KEY") or os.getenv("API_KEY")
    if value and value.strip():
        return value.strip()
    return None


def _extract_token(request: Request) -> str | None:
    header_key = request.headers.get("x-api-key")
    if header_key:
        return header_key.strip()
    authorization = request.headers.get("authorization") or ""
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


def install_api_key_auth(app: FastAPI, public_paths: Iterable[str] = PUBLIC_PATHS) -> None:
    public = set(public_paths)

    @app.middleware("http")
    async def api_key_auth_middleware(request: Request, call_next):
        if request.url.path in public:
            return await call_next(request)

        expected = _env_api_key()
        if expected is None:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "failed",
                    "error": "api_key_not_configured",
                    "detail": "Set API_KEY or VELOCITY_CLAW_API_KEY before exposing the API.",
                },
            )

        supplied = _extract_token(request)
        if not supplied or not compare_digest(supplied, expected):
            return JSONResponse(
                status_code=401,
                content={
                    "status": "failed",
                    "error": "unauthorized",
                    "detail": "Provide X-API-Key or Authorization: Bearer token.",
                },
            )

        return await call_next(request)
