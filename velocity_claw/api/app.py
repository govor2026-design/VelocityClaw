from __future__ import annotations

from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from velocity_claw.api.approval_v2 import (
    approve_with_guard,
    build_approval_detail,
    build_approval_index,
    reject_with_guard,
)
from velocity_claw.api.auth import install_api_key_auth
from velocity_claw.api.dashboard_v2 import render_dashboard_v2
from velocity_claw.api.diagnostics_v2 import build_diagnostics_v2
from velocity_claw.api.errors import install_api_error_handlers
from velocity_claw.api.ops_console import build_operations_console
from velocity_claw.api.run_detail_v2 import build_artifact_index, build_run_detail_v2
from velocity_claw.api.server import ApprovalDecisionRequest, create_app as create_base_app
from velocity_claw.api.version import build_version_payload


def install_version_endpoint(app: FastAPI) -> None:
    @app.get("/version")
    def version():
        return build_version_payload(app.state.settings)


def _prepare_forced_retry(queue, job) -> None:
    if job.attempts < queue.max_attempts:
        return
    previous_attempts = job.attempts
    job.attempts = 0
    job.updated_at = datetime.now().isoformat()
    job.history.append(
        {
            "status": "queued",
            "reason": "forced_retry_cycle_reset",
            "at": job.updated_at,
            "attempts": 0,
            "previous_attempts": previous_attempts,
        }
    )
    queue._persist_job(job)


def install_queue_persistence_v2(app: FastAPI) -> None:
    from velocity_claw.core.queue_tracking import install_direct_run_tracking

    settings = getattr(app.state, "settings", None)
    if settings is not None and hasattr(app.state.queue, "configure_runtime"):
        app.state.queue.configure_runtime(
            max_concurrency=getattr(settings, "queue_max_concurrency", app.state.queue.max_concurrency),
            max_attempts=getattr(settings, "queue_max_attempts", 3),
            recover_on_startup=getattr(settings, "queue_recover_on_startup", True),
        )
    install_direct_run_tracking(app.state.queue)

    async def startup_queue_recovery() -> None:
        scheduled = app.state.queue.resume(app.state.agent.run_task)
        app.state.queue_startup_schedule = {
            "scheduled_job_ids": scheduled,
            "scheduled_count": len(scheduled),
            "runtime": app.state.queue.runtime_summary(),
        }
        if scheduled:
            app.state.logger.info("Recovered and scheduled %s persisted queue jobs", len(scheduled))

    async def shutdown_queue_workers() -> None:
        timeout = getattr(settings, "queue_shutdown_timeout_seconds", 10) if settings is not None else 10
        app.state.queue_shutdown = await app.state.queue.shutdown(timeout_seconds=timeout, cancel_running=True)
        if app.state.queue_shutdown.get("timed_out"):
            app.state.logger.warning("Queue shutdown timed out with %s pending tasks", app.state.queue_shutdown["pending_tasks"])

    app.router.add_event_handler("startup", startup_queue_recovery)
    app.router.add_event_handler("shutdown", shutdown_queue_workers)

    @app.get("/queue/v2/runtime")
    def queue_runtime_v2():
        return {
            "status": "ok",
            "queue": app.state.queue.runtime_summary(),
            "jobs": app.state.queue.list_jobs()[:20],
        }

    @app.post("/queue/v2/recover")
    async def queue_recover_v2():
        scheduled = app.state.queue.schedule_pending(app.state.agent.run_task)
        return {
            "status": "ok",
            "scheduled_job_ids": scheduled,
            "scheduled_count": len(scheduled),
            "queue": app.state.queue.runtime_summary(),
        }

    @app.post("/queue/v2/pause")
    def queue_pause_v2():
        return {"status": "ok", "queue": app.state.queue.pause()}

    @app.post("/queue/v2/resume")
    async def queue_resume_v2():
        scheduled = app.state.queue.resume(app.state.agent.run_task)
        return {
            "status": "ok",
            "scheduled_job_ids": scheduled,
            "scheduled_count": len(scheduled),
            "queue": app.state.queue.runtime_summary(),
        }

    @app.post("/queue/v2/drain")
    async def queue_drain_v2(timeout_seconds: float = 10.0):
        if timeout_seconds < 0 or timeout_seconds > 3600:
            raise HTTPException(
                status_code=400,
                detail={"status": "failed", "error": "invalid_timeout", "detail": "timeout_seconds must be between 0 and 3600"},
            )
        return await app.state.queue.drain(timeout_seconds=timeout_seconds)

    @app.post("/queue/v2/{job_id}/requeue")
    async def queue_requeue_v2(job_id: str, force: bool = False):
        existing = app.state.queue.get(job_id)
        if not existing:
            raise HTTPException(status_code=404, detail={"status": "failed", "error": "not_found", "detail": "Job not found"})
        if existing.status == "completed":
            raise HTTPException(
                status_code=409,
                detail={"status": "failed", "error": "job_not_requeueable", "detail": "Completed jobs cannot be requeued"},
            )

        job = app.state.queue.requeue(job_id, force=force)
        if job.status == "failed" and job.terminal_reason == "max_attempts_exhausted" and not force:
            raise HTTPException(
                status_code=409,
                detail={
                    "status": "failed",
                    "error": "max_attempts_exhausted",
                    "detail": {"job_id": job_id, "attempts": job.attempts, "max_attempts": app.state.queue.max_attempts},
                },
            )
        if force and job.status == "queued":
            _prepare_forced_retry(app.state.queue, job)
        scheduled = app.state.queue.schedule(job_id, app.state.agent.run_task) if job.status == "queued" else False
        return {
            "status": "ok",
            "job": job.__dict__,
            "scheduled": scheduled,
            "queue": app.state.queue.runtime_summary(),
        }

    @app.post("/queue/v2/{job_id}/cancel")
    def queue_cancel_v2(job_id: str):
        job = app.state.queue.cancel(job_id)
        if not job:
            raise HTTPException(status_code=404, detail={"status": "failed", "error": "not_found", "detail": "Job not found"})
        return {
            "status": "ok",
            "job": job.__dict__,
            "queue": app.state.queue.runtime_summary(),
        }


def install_approval_v2(app: FastAPI) -> None:
    @app.get("/approvals/v2")
    def approval_index_v2(limit: int = 50, risk: str | None = None, tool: str | None = None):
        return build_approval_index(
            app.state.agent,
            limit=limit,
            risk=risk,
            tool=tool,
        )

    @app.get("/approvals/v2/{run_id}/{step_id}")
    def approval_detail_v2(run_id: str, step_id: int):
        detail = build_approval_detail(app.state.agent.memory.load_run(run_id), step_id)
        if detail["status"] == "not_found":
            raise HTTPException(status_code=404, detail={"status": "failed", "error": detail["reason"], "detail": detail})
        return {"status": "ok", "approval": detail}

    @app.post("/approvals/v2/{run_id}/{step_id}/approve")
    async def approve_v2(run_id: str, step_id: int, payload: ApprovalDecisionRequest):
        result = await approve_with_guard(app.state.agent, run_id, step_id, actor=payload.actor, reason=payload.reason)
        if result.get("status") == "blocked":
            raise HTTPException(status_code=409, detail={"status": "failed", "error": result["reason"], "detail": result})
        return result

    @app.post("/approvals/v2/{run_id}/{step_id}/reject")
    def reject_v2(run_id: str, step_id: int, payload: ApprovalDecisionRequest):
        result = reject_with_guard(app.state.agent, run_id, step_id, actor=payload.actor, reason=payload.reason)
        if result.get("status") == "blocked":
            raise HTTPException(status_code=409, detail={"status": "failed", "error": result["reason"], "detail": result})
        return result


def install_run_detail_v2(app: FastAPI) -> None:
    @app.get("/runs/{run_id}/detail/v2")
    def run_detail_v2(run_id: str):
        run = app.state.agent.memory.load_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail={"status": "failed", "error": "not_found", "detail": "Run not found"})
        return {"status": "ok", "run": build_run_detail_v2(run)}

    @app.get("/runs/{run_id}/artifacts/v2")
    def run_artifacts_v2(run_id: str):
        run = app.state.agent.memory.load_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail={"status": "failed", "error": "not_found", "detail": "Run not found"})
        return {"status": "ok", "run_id": run_id, "artifacts": build_artifact_index(run)}


def install_diagnostics_v2(app: FastAPI) -> None:
    @app.get("/diagnostics/v2")
    def diagnostics_v2():
        release_state = app.state.release.evaluate()
        queue_jobs = app.state.queue.list_jobs()
        approvals = app.state.agent.list_pending_approvals()
        provider_observability = app.state.agent.router.get_router_observability()
        provider_health = app.state.agent.router.get_provider_health()
        last_failed = app.state.agent.resume_last_failed_run()
        metrics = app.state.metrics.snapshot()
        queue_runtime = app.state.queue.runtime_summary() if hasattr(app.state.queue, "runtime_summary") else None
        return build_diagnostics_v2(
            settings=app.state.settings,
            release_state=release_state,
            queue_jobs=queue_jobs,
            approvals=approvals,
            provider_observability=provider_observability,
            provider_health=provider_health,
            last_failed=last_failed,
            metrics=metrics,
            active_workers=app.state.queue.active_count(),
            max_concurrency=app.state.queue.max_concurrency,
            queue_runtime=queue_runtime,
        )


def install_dashboard_v2(app: FastAPI) -> None:
    @app.get("/dashboard/v2", response_class=HTMLResponse)
    def dashboard_v2():
        if hasattr(app.state, "metrics"):
            app.state.metrics.set_value("approvals_pending", len(app.state.agent.list_pending_approvals()))
            queue_jobs_for_metrics = app.state.queue.list_jobs()
            app.state.metrics.set_value("queue_total", len(queue_jobs_for_metrics))
            app.state.metrics.set_value("queue_running", sum(1 for job in queue_jobs_for_metrics if job["status"] == "running"))
            app.state.metrics.set_value("queue_failed", sum(1 for job in queue_jobs_for_metrics if job["status"] == "failed"))
            app.state.metrics.set_value("queue_cancelled", sum(1 for job in queue_jobs_for_metrics if job["status"] == "cancelled"))

        release_state = app.state.release.evaluate()
        queue_jobs = app.state.queue.list_jobs()
        approvals = app.state.agent.list_pending_approvals()
        provider_observability = app.state.agent.router.get_router_observability()
        provider_health = app.state.agent.router.get_provider_health()
        last_failed = app.state.agent.resume_last_failed_run()
        metrics = app.state.metrics.snapshot()
        console_snapshot = build_operations_console(
            release_state=release_state,
            queue_jobs=queue_jobs,
            approvals=approvals,
            provider_observability=provider_observability,
            last_failed=last_failed,
            metrics=metrics,
            active_workers=app.state.queue.active_count(),
            max_concurrency=app.state.queue.max_concurrency,
        )

        return render_dashboard_v2(
            execution_profile=app.state.settings.execution_profile,
            safe_mode=app.state.settings.safe_mode,
            trusted_mode=app.state.settings.trusted_mode,
            release_state=release_state,
            console=console_snapshot,
            recent_runs=app.state.agent.memory.list_recent_runs(limit=10),
            approvals=approvals,
            queue_jobs=queue_jobs[:10],
            metrics=metrics,
            provider_observability=provider_observability,
            provider_health=provider_health,
            last_failed=last_failed,
        )


def create_app() -> FastAPI:
    """Create the production API app with shared hardening installed."""
    app = create_base_app()
    install_api_error_handlers(app)
    install_version_endpoint(app)
    install_queue_persistence_v2(app)
    install_approval_v2(app)
    install_run_detail_v2(app)
    install_diagnostics_v2(app)
    install_dashboard_v2(app)
    install_api_key_auth(app)
    app.state.api_error_handlers_installed = True
    app.state.version_endpoint_installed = True
    app.state.queue_persistence_v2_installed = True
    app.state.queue_orchestration_v2_installed = True
    app.state.approval_v2_installed = True
    app.state.run_detail_v2_installed = True
    app.state.diagnostics_v2_installed = True
    app.state.dashboard_v2_installed = True
    app.state.api_key_auth_installed = True
    return app
