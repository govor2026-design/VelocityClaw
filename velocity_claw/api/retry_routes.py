from __future__ import annotations

from typing import Any, Callable

from fastapi import HTTPException


def register_retry_routes(app, ok: Callable[..., dict]) -> None:
    @app.get("/runs/{run_id}/retry-context")
    def run_retry_context(run_id: str) -> dict:
        try:
            return ok("retry_context", app.state.agent.build_retry_context(run_id), run_id=run_id)
        except ValueError as exc:
            if str(exc) == "run_not_found":
                raise HTTPException(status_code=404, detail={"status": "failed", "error": "not_found", "detail": "Run not found"})
            raise

    @app.post("/runs/{run_id}/retry")
    async def retry_run(run_id: str) -> dict[str, Any]:
        try:
            result = await app.state.agent.retry_run(run_id)
            return ok("retry", result, run_id=run_id)
        except ValueError as exc:
            if str(exc) == "run_not_found":
                raise HTTPException(status_code=404, detail={"status": "failed", "error": "not_found", "detail": "Run not found"})
            raise
