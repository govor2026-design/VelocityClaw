from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from velocity_claw.core.failed_run_resume import (
    FailedRunResumeError,
    install_failed_run_resume_instance,
)


class ResumeFailedRunRequest(BaseModel):
    actor: str = "operator"
    reason: str | None = None


def _raise_http(exc: FailedRunResumeError) -> None:
    raise HTTPException(
        status_code=exc.status_code,
        detail={
            "status": "failed",
            "error": exc.code,
            "detail": exc.detail,
        },
    ) from exc


def install_failed_run_resume_v2(app: FastAPI) -> None:
    install_failed_run_resume_instance(app.state.agent)

    @app.get("/runs/{run_id}/resume/v2")
    def failed_run_resume_preview_v2(run_id: str):
        try:
            preview = app.state.agent.get_failed_run_resume_state(run_id)
        except FailedRunResumeError as exc:
            _raise_http(exc)
        return {"status": "ok", "resume": preview}

    @app.post("/runs/{run_id}/resume/v2")
    async def failed_run_resume_v2(run_id: str, payload: ResumeFailedRunRequest):
        try:
            result = await app.state.agent.resume_failed_run(
                run_id,
                actor=payload.actor,
                reason=payload.reason,
            )
        except FailedRunResumeError as exc:
            _raise_http(exc)
        return {"status": "ok", "resume": result}
