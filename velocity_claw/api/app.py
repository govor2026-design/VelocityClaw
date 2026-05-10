from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from velocity_claw.api.auth import install_api_key_auth
from velocity_claw.api.dashboard_v2 import render_dashboard_v2
from velocity_claw.api.errors import install_api_error_handlers
from velocity_claw.api.server import create_app as create_base_app


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
        console = app.routes[1].endpoint.__globals__.get("build_operations_console") if False else None

        from velocity_claw.api.ops_console import build_operations_console

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
    install_dashboard_v2(app)
    install_api_key_auth(app)
    app.state.api_error_handlers_installed = True
    app.state.dashboard_v2_installed = True
    app.state.api_key_auth_installed = True
    return app
