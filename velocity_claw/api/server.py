from typing import Any, Dict, List, Optional
import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from velocity_claw.config.settings import load_settings
from velocity_claw.core.agent import VelocityClawAgent
from velocity_claw.core.queue import RunQueue
from velocity_claw.core.metrics import MetricsRegistry
from velocity_claw.logs.logger import get_logger
from velocity_claw.security.policy import SecurityViolationError
from velocity_claw.security.access import ExecutionProfileManager


class TaskRequest(BaseModel):
    task: str
    context: Optional[Dict[str, Any]] = None


class StepResponse(BaseModel):
    id: int
    title: str
    tool: Optional[str] = None
    args: Optional[Dict[str, Any]] = None
    status: str
    result: Optional[Any] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class TaskResponse(BaseModel):
    run_id: str
    task: str
    status: str
    summary: str
    steps: List[StepResponse]
    signature: str


class StatusResponse(BaseModel):
    status: str
    env: str
    safe_mode: bool
    trusted_mode: bool
    memory_enabled: bool
    execution_profile: str
    available_modes: List[str]
    signature: str


class ResetResponse(BaseModel):
    status: str
    signature: str


class AutoFixRequest(BaseModel):
    target_test: str
    patch_plan: List[Dict[str, Any]]
    runner: str = "pytest"
    max_attempts: int = 2


class ModeRequest(BaseModel):
    mode: str
    task: str
    context: Optional[Dict[str, Any]] = None


class ApprovalDecisionRequest(BaseModel):
    actor: str = "owner"
    reason: Optional[str] = None


def create_app() -> FastAPI:
    settings = load_settings()
    app = FastAPI(title="Velocity Claw API")
    app.state.settings = settings
    app.state.logger = get_logger("velocity_claw.api")
    app.state.agent = VelocityClawAgent(settings=settings)
    app.state.queue = RunQueue()
    app.state.metrics = MetricsRegistry()
    app.state.profiles = ExecutionProfileManager(settings)

    @app.get("/health")
    def health():
        return {"status": "ok", "metrics": app.state.metrics.snapshot()}

    @app.post("/task", response_model=TaskResponse)
    async def task(request: TaskRequest):
        if not request.task or not request.task.strip():
            raise HTTPException(status_code=400, detail={"status": "failed", "error": "invalid_task", "detail": "Task must not be empty"})
        app.state.metrics.incr("tasks_total")
        try:
            result = await app.state.agent.run_task(request.task, request.context)
            app.state.metrics.incr("tasks_completed")
            return TaskResponse(**result)
        except SecurityViolationError as e:
            app.state.metrics.incr("tasks_failed")
            app.state.logger.warning("Task blocked by security policy: %s", e)
            raise HTTPException(status_code=403, detail={"status": "failed", "error": "security_block", "detail": str(e)})
        except ValueError as e:
            app.state.metrics.incr("tasks_failed")
            app.state.logger.warning("Task rejected: %s", e)
            raise HTTPException(status_code=400, detail={"status": "failed", "error": "invalid_request", "detail": str(e)})
        except Exception as e:
            app.state.metrics.incr("tasks_failed")
            app.state.logger.error("Task execution failed: %s", e)
            raise HTTPException(status_code=500, detail={"status": "failed", "error": "internal_error", "detail": str(e)})

    @app.post("/modes/run")
    async def run_mode(request: ModeRequest):
        app.state.metrics.incr("tasks_total")
        result = await app.state.agent.run_mode(request.mode, request.task, request.context)
        if result["status"] == "completed":
            app.state.metrics.incr("tasks_completed")
        else:
            app.state.metrics.incr("tasks_failed")
        return result

    @app.get("/modes")
    def modes():
        return {"modes": app.state.agent.get_status()["available_modes"]}

    @app.get("/profiles")
    def profiles():
        return {"active": app.state.settings.execution_profile, "profiles": app.state.profiles.list_profiles()}

    @app.get("/profiles/active")
    def active_profile():
        return app.state.profiles.get_capability_matrix()

    @app.get("/profiles/explain/{tool_name}")
    def explain_profile_tool(tool_name: str):
        tool = tool_name.replace("__", ".")
        return app.state.profiles.explain_tool_access(tool)

    @app.post("/queue/submit")
    async def queue_submit(request: TaskRequest):
        job = app.state.queue.enqueue(request.task, request.context)
        asyncio.create_task(app.state.queue.run_job(job.job_id, app.state.agent.run_task))
        return {"job_id": job.job_id, "status": job.status}

    @app.get("/queue/{job_id}")
    def queue_status(job_id: str):
        job = app.state.queue.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail={"status": "failed", "error": "not_found", "detail": "Job not found"})
        return job.__dict__

    @app.post("/auto-fix")
    def auto_fix(request: AutoFixRequest):
        app.state.metrics.incr("auto_fix_total")
        return app.state.agent.run_auto_fix(
            target_test=request.target_test,
            patch_plan=request.patch_plan,
            runner=request.runner,
            max_attempts=request.max_attempts,
        )

    @app.get("/status", response_model=StatusResponse)
    def status():
        app.state.metrics.set_value("approvals_pending", len(app.state.agent.list_pending_approvals()))
        return StatusResponse(**app.state.agent.get_status())

    @app.get("/metrics")
    def metrics():
        app.state.metrics.set_value("approvals_pending", len(app.state.agent.list_pending_approvals()))
        return app.state.metrics.snapshot()

    @app.post("/reset", response_model=ResetResponse)
    def reset():
        return ResetResponse(**app.state.agent.reset_context())

    @app.get("/runs")
    def runs():
        return {"recent": app.state.agent.memory.list_recent_runs(), "last_failed": app.state.agent.resume_last_failed_run()}

    @app.get("/runs/{run_id}")
    def run_detail(run_id: str):
        data = app.state.agent.memory.load_run(run_id)
        if not data:
            raise HTTPException(status_code=404, detail={"status": "failed", "error": "not_found", "detail": "Run not found"})
        return data

    @app.get("/runs/{run_id}/approval-history")
    def approval_history(run_id: str):
        return {"run_id": run_id, "history": app.state.agent.get_approval_history(run_id)}

    @app.get("/approvals")
    def approvals():
        return {"pending": app.state.agent.list_pending_approvals()}

    @app.post("/approvals/{run_id}/{step_id}/approve")
    def approve(run_id: str, step_id: int, request: ApprovalDecisionRequest):
        return app.state.agent.approve_step(run_id, step_id, actor=request.actor, reason=request.reason)

    @app.post("/approvals/{run_id}/{step_id}/reject")
    def reject(run_id: str, step_id: int, request: ApprovalDecisionRequest):
        return app.state.agent.reject_step(run_id, step_id, actor=request.actor, reason=request.reason)

    @app.get("/dashboard", response_class=HTMLResponse)
    def dashboard():
        recent = app.state.agent.memory.list_recent_runs(limit=10)
        approvals = app.state.agent.list_pending_approvals()
        profile = app.state.profiles.get_capability_matrix()

        def badge(status: str) -> str:
            return f"<span style='padding:2px 8px;border-radius:999px;border:1px solid #999'>{status}</span>"

        body = [
            "<html><body style='font-family:Arial,sans-serif;max-width:1100px;margin:24px auto;padding:0 16px'>",
            "<h1>Velocity Claw Dashboard</h1>",
            f"<p>Execution profile: <b>{app.state.settings.execution_profile}</b></p>",
            "<h2>Active profile matrix</h2>",
            f"<p>{profile['description']}</p>",
            "<ul>",
        ]
        for key, value in profile["capabilities"].items():
            body.append(f"<li>{key}: <b>{value}</b></li>")
        body.append("</ul>")

        body.append("<h2>Recent runs</h2>")
        body.append("<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse;width:100%'>")
        body.append("<tr><th>Run ID</th><th>Task</th><th>Status</th><th>Created</th></tr>")
        for run in recent:
            body.append(
                f"<tr><td><code>{run['run_id']}</code></td><td>{run['task']}</td><td>{badge(run['status'])}</td><td>{run['created_at']}</td></tr>"
            )
        body.append("</table>")

        body.append("<h2>Pending approvals</h2>")
        if approvals:
            body.append("<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse;width:100%'>")
            body.append("<tr><th>Run ID</th><th>Step</th><th>Tool</th><th>Reason</th></tr>")
            for item in approvals:
                reason = (item.get("result") or {}).get("reason") if isinstance(item.get("result"), dict) else None
                body.append(
                    f"<tr><td><code>{item['run_id']}</code></td><td>{item['title']}</td><td>{item['tool']}</td><td>{reason or 'n/a'}</td></tr>"
                )
            body.append("</table>")
        else:
            body.append("<p>No pending approvals.</p>")

        body.append("</body></html>")
        return "".join(body)

    return app
