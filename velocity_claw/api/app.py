from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from velocity_claw.api.approval_v2 import approve_with_guard, build_approval_detail, reject_with_guard
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


def install_approval_v2(app: FastAPI) -> None:
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
    install_approval_v2(app)
    install_run_detail_v2(app)
    install_diagnostics_v2(app)
    install_dashboard_v2(app)
    install_api_key_auth(app)
    app.state.api_error_handlers_installed = True
    app.state.version_endpoint_installed = True
    app.state.approval_v2_installed = True
    app.state.run_detail_v2_installed = True
    app.state.diagnostics_v2_installed = True
    app.state.dashboard_v2_installed = True
    app.state.api_key_auth_installed = True
    return app
