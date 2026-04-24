from typing import Any, Dict, List, Optional
import asyncio
import json
import time
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from velocity_claw.api.ops_console import build_operations_console
from velocity_claw.config.settings import load_settings
from velocity_claw.core.agent import VelocityClawAgent
from velocity_claw.core.queue import RunQueue
from velocity_claw.core.metrics import MetricsRegistry
from velocity_claw.core.release import ReleaseReadinessEvaluator
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


class ApprovalExplainRequest(BaseModel):
    step: Dict[str, Any]
    profile_name: Optional[str] = None


limiter = Limiter(key_func=get_remote_address)


def create_app() -> FastAPI:
    settings = load_settings()
    app = FastAPI(title="Velocity Claw API")
    app.state.settings = settings
    app.state.logger = get_logger("velocity_claw.api")
    app.state.agent = VelocityClawAgent(settings=settings)
    app.state.queue = RunQueue(db_path=f"{settings.memory_db_path}.queue", max_concurrency=2)
    app.state.metrics = MetricsRegistry()
    app.state.profiles = ExecutionProfileManager(settings)
    app.state.release = ReleaseReadinessEvaluator(settings)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    def ok(payload_key: str, payload: Any, **extra: Any) -> dict:
        body = {"status": "ok", payload_key: payload}
        body.update(extra)
        return body

    def refresh_runtime_metrics() -> None:
        approvals_pending = len(app.state.agent.list_pending_approvals())
        queue_jobs = app.state.queue.list_jobs()
        app.state.metrics.set_value("approvals_pending", approvals_pending)
        app.state.metrics.set_value("queue_total", len(queue_jobs))
        app.state.metrics.set_value("queue_running", sum(1 for job in queue_jobs if job["status"] == "running"))
        app.state.metrics.set_value("queue_failed", sum(1 for job in queue_jobs if job["status"] == "failed"))
        app.state.metrics.set_value("queue_cancelled", sum(1 for job in queue_jobs if job["status"] == "cancelled"))

    def group_artifacts(run_data: dict) -> dict:
        grouped: dict[str, list[dict]] = {}
        for artifact in run_data.get("artifacts", []):
            key = f"step_{artifact['step_id']}" if artifact.get("step_id") is not None else "run_level"
            grouped.setdefault(key, []).append(artifact)
        return grouped

    def load_artifact_json(run_data: dict, artifact_name: str) -> Optional[dict]:
        for artifact in run_data.get("artifacts", []):
            if artifact.get("name") == artifact_name:
                try:
                    return json.loads(artifact.get("content") or "{}")
                except json.JSONDecodeError:
                    return {"raw": artifact.get("content")}
        return None

    def build_console_snapshot() -> dict:
        refresh_runtime_metrics()
        release_state = app.state.release.evaluate()
        queue_jobs = app.state.queue.list_jobs()
        approvals = app.state.agent.list_pending_approvals()
        provider_observability = app.state.agent.router.get_router_observability()
        last_failed = app.state.agent.resume_last_failed_run()
        metrics = app.state.metrics.snapshot()
        return build_operations_console(
            release_state=release_state,
            queue_jobs=queue_jobs,
            approvals=approvals,
            provider_observability=provider_observability,
            last_failed=last_failed,
            metrics=metrics,
            active_workers=app.state.queue.active_count(),
            max_concurrency=app.state.queue.max_concurrency,
        )

    @app.get("/health")
    def health():
        refresh_runtime_metrics()
        return ok("metrics", app.state.metrics.snapshot())

    @app.get("/ops/console")
    def ops_console():
        snapshot = build_console_snapshot()
        snapshot["status"] = "ok"
        return snapshot

    @app.get("/release/readiness")
    def release_readiness():
        return ok("release", app.state.release.evaluate())

    @app.post("/task", response_model=TaskResponse)
    @limiter.limit("10/minute")
    async def task(request: Request, payload: TaskRequest):
        if not payload.task or not payload.task.strip():
            raise HTTPException(status_code=400, detail={"status": "failed", "error": "invalid_task", "detail": "Task must not be empty"})
        app.state.metrics.incr("tasks_total")
        started = time.monotonic()
        try:
            result = await app.state.agent.run_task(payload.task, payload.context)
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
        finally:
            app.state.metrics.observe_task_duration(int((time.monotonic() - started) * 1000))
            refresh_runtime_metrics()

    @app.post("/modes/run")
    @limiter.limit("10/minute")
    async def run_mode(request: Request, payload: ModeRequest):
        app.state.metrics.incr("tasks_total")
        started = time.monotonic()
        try:
            result = await app.state.agent.run_mode(payload.mode, payload.task, payload.context)
            if result["status"] == "completed":
                app.state.metrics.incr("tasks_completed")
            else:
                app.state.metrics.incr("tasks_failed")
            return result
        finally:
            app.state.metrics.observe_task_duration(int((time.monotonic() - started) * 1000))
            refresh_runtime_metrics()

    @app.get("/modes")
    def modes():
        return ok("modes", app.state.agent.get_status()["available_modes"])

    @app.get("/profiles")
    def profiles():
        return ok("profiles", app.state.profiles.list_profiles(), active=app.state.settings.execution_profile)

    @app.get("/profiles/active")
    def active_profile():
        return ok("profile", app.state.profiles.get_capability_matrix())

    @app.get("/profiles/explain/{tool_name}")
    def explain_profile_tool(tool_name: str):
        tool = tool_name.replace("__", ".")
        return ok("explanation", app.state.profiles.explain_tool_access(tool), tool=tool)

    @app.get("/providers/health")
    def provider_health():
        return ok("providers", app.state.agent.router.get_provider_health())

    @app.get("/providers/observability")
    def provider_observability():
        return ok("observability", app.state.agent.router.get_router_observability())

    @app.get("/git/summary")
    def git_summary():
        return ok("git", app.state.agent.executor.git.inspect_repo())

    @app.get("/memory/context")
    def memory_context():
        return ok("context", app.state.agent.get_repo_context_summary())

    @app.get("/memory/resume")
    def memory_resume(task: str):
        return ok("resume", app.state.agent.get_resume_context(task), task=task)

    @app.post("/approvals/explain")
    def explain_approval(payload: ApprovalExplainRequest):
        return ok("explanation", app.state.agent.explain_approval_requirement(payload.step, payload.profile_name))

    @app.post("/queue/submit")
    @limiter.limit("10/minute")
    async def queue_submit(request: Request, payload: TaskRequest):
        job = app.state.queue.enqueue(payload.task, payload.context)
        refresh_runtime_metrics()
        asyncio.create_task(app.state.queue.run_job(job.job_id, app.state.agent.run_task))
        return ok("job", {"job_id": job.job_id, "status": job.status})

    @app.get("/queue")
    def queue_list():
        refresh_runtime_metrics()
        return ok("jobs", app.state.queue.list_jobs(), active_workers=app.state.queue.active_count(), max_concurrency=app.state.queue.max_concurrency)

    @app.get("/queue/{job_id}")
    def queue_status(job_id: str):
        job = app.state.queue.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail={"status": "failed", "error": "not_found", "detail": "Job not found"})
        refresh_runtime_metrics()
        return ok("job", job.__dict__)

    @app.post("/queue/{job_id}/cancel")
    @limiter.limit("20/minute")
    def queue_cancel(request: Request, job_id: str):
        job = app.state.queue.cancel(job_id)
        if not job:
            raise HTTPException(status_code=404, detail={"status": "failed", "error": "not_found", "detail": "Job not found"})
        refresh_runtime_metrics()
        return ok("job", job.__dict__)

    @app.post("/queue/{job_id}/requeue")
    @limiter.limit("20/minute")
    def queue_requeue(request: Request, job_id: str):
        job = app.state.queue.requeue(job_id)
        if not job:
            raise HTTPException(status_code=404, detail={"status": "failed", "error": "not_found", "detail": "Job not found"})
        refresh_runtime_metrics()
        return ok("job", job.__dict__)

    @app.post("/auto-fix")
    @limiter.limit("5/minute")
    def auto_fix(request: Request, payload: AutoFixRequest):
        app.state.metrics.incr("auto_fix_total")
        refresh_runtime_metrics()
        return app.state.agent.run_auto_fix(
            target_test=payload.target_test,
            patch_plan=payload.patch_plan,
            runner=payload.runner,
            max_attempts=payload.max_attempts,
        )

    @app.get("/status", response_model=StatusResponse)
    def status():
        refresh_runtime_metrics()
        return StatusResponse(**app.state.agent.get_status())

    @app.get("/metrics")
    def metrics():
        refresh_runtime_metrics()
        return ok("metrics", app.state.metrics.snapshot())

    @app.get("/diagnostics")
    def diagnostics():
        refresh_runtime_metrics()
        return ok("diagnostics", {
            "metrics": app.state.metrics.snapshot(),
            "diagnostics": app.state.metrics.diagnostics_summary(),
            "last_failed_run": app.state.agent.resume_last_failed_run(),
            "queue_jobs_preview": app.state.queue.list_jobs()[:10],
            "active_workers": app.state.queue.active_count(),
            "max_concurrency": app.state.queue.max_concurrency,
            "provider_health": app.state.agent.router.get_provider_health(),
            "provider_observability": app.state.agent.router.get_router_observability(),
        })

    @app.post("/reset", response_model=ResetResponse)
    def reset():
        return ResetResponse(**app.state.agent.reset_context())

    @app.get("/runs")
    def runs():
        return ok("runs", app.state.agent.memory.list_recent_runs(), last_failed=app.state.agent.resume_last_failed_run())

    @app.get("/runs/{run_id}")
    def run_detail(run_id: str):
        data = app.state.agent.memory.load_run(run_id)
        if not data:
            raise HTTPException(status_code=404, detail={"status": "failed", "error": "not_found", "detail": "Run not found"})
        return ok("run", data)

    @app.get("/runs/{run_id}/forensics")
    def run_forensics(run_id: str):
        data = app.state.agent.memory.load_run(run_id)
        if not data:
            raise HTTPException(status_code=404, detail={"status": "failed", "error": "not_found", "detail": "Run not found"})
        return ok("forensics", data.get("forensics", {}), run_id=run_id)

    @app.get("/runs/{run_id}/artifacts")
    def run_artifacts(run_id: str):
        data = app.state.agent.memory.load_run(run_id)
        if not data:
            raise HTTPException(status_code=404, detail={"status": "failed", "error": "not_found", "detail": "Run not found"})
        return ok("artifacts", group_artifacts(data), run_id=run_id)

    @app.get("/runs/{run_id}/planning-context")
    def run_planning_context(run_id: str):
        data = app.state.agent.memory.load_run(run_id)
        if not data:
            raise HTTPException(status_code=404, detail={"status": "failed", "error": "not_found", "detail": "Run not found"})
        planning_context = load_artifact_json(data, "planning_context")
        if planning_context is None:
            raise HTTPException(status_code=404, detail={"status": "failed", "error": "not_found", "detail": "Planning context not found"})
        return ok("planning_context", planning_context, run_id=run_id)

    @app.get("/runs/{run_id}/resume-context")
    def run_resume_context(run_id: str):
        data = app.state.agent.memory.load_run(run_id)
        if not data:
            raise HTTPException(status_code=404, detail={"status": "failed", "error": "not_found", "detail": "Run not found"})
        resume_context = load_artifact_json(data, "resume_context")
        if resume_context is None:
            raise HTTPException(status_code=404, detail={"status": "failed", "error": "not_found", "detail": "Resume context not found"})
        return ok("resume_context", resume_context, run_id=run_id)

    @app.get("/runs/{run_id}/report")
    def run_report(run_id: str):
        data = app.state.agent.memory.load_run(run_id)
        if not data:
            raise HTTPException(status_code=404, detail={"status": "failed", "error": "not_found", "detail": "Run not found"})
        return ok("report", data.get("report", {}), run_id=run_id)

    @app.get("/runs/{run_id}/view", response_class=HTMLResponse)
    def run_detail_view(run_id: str):
        data = app.state.agent.memory.load_run(run_id)
        if not data:
            raise HTTPException(status_code=404, detail={"status": "failed", "error": "not_found", "detail": "Run not found"})
        grouped = group_artifacts(data)
        planning_context = load_artifact_json(data, "planning_context")
        resume_context = load_artifact_json(data, "resume_context")
        forensics = data.get("forensics") or {}
        report = data.get("report") or {}
        body = [
            "<html><body style='font-family:Arial,sans-serif;max-width:1100px;margin:24px auto;padding:0 16px'>",
            f"<h1>Run detail: {run_id}</h1>",
            f"<p>Task: <b>{data['task']}</b></p>",
            f"<p>Status: <b>{data['status']}</b></p>",
            f"<p>Created: {data['created_at']}</p>",
            "<h2>Run report</h2>",
            f"<p>{report.get('executive_summary') or 'No report summary available.'}</p>",
            "<h2>Run forensics</h2>",
            f"<p>Steps: <b>{forensics.get('step_count', 0)}</b> | Artifacts: <b>{forensics.get('artifact_count', 0)}</b></p>",
            f"<pre>{json.dumps(forensics, ensure_ascii=False, indent=2)[:2500]}</pre>",
            "<h2>Steps</h2>",
            "<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse;width:100%'>",
            "<tr><th>ID</th><th>Title</th><th>Tool</th><th>Status</th><th>Error</th></tr>",
        ]
        for step in data.get("steps", []):
            body.append(f"<tr><td>{step['id']}</td><td>{step['title']}</td><td>{step.get('tool') or ''}</td><td>{step['status']}</td><td>{step.get('error') or ''}</td></tr>")
        body.append("</table>")
        body.append("<h2>Planning context</h2>")
        if planning_context:
            body.append(f"<pre>{json.dumps(planning_context, ensure_ascii=False, indent=2)[:2000]}</pre>")
        else:
            body.append("<p>No planning context artifact recorded for this run.</p>")
        body.append("<h2>Resume context</h2>")
        if resume_context:
            body.append(f"<pre>{json.dumps(resume_context, ensure_ascii=False, indent=2)[:2000]}</pre>")
        else:
            body.append("<p>No resume context artifact recorded for this run.</p>")
        body.append("<h2>Approval history</h2><ul>")
        for item in data.get("approval_history", []):
            body.append(f"<li>step {item['step_id']} — {item['decision']} — actor: {item.get('actor') or 'n/a'} — reason: {item.get('reason') or 'n/a'}</li>")
        body.append("</ul>")
        body.append("<h2>Artifacts</h2>")
        for group_name, artifacts in grouped.items():
            body.append(f"<h3>{group_name}</h3><ul>")
            for artifact in artifacts:
                preview = (artifact.get('content') or '')[:180].replace('<', '&lt;').replace('>', '&gt;')
                body.append(f"<li>{artifact['name']} [{artifact['artifact_type']}]<pre>{preview}</pre></li>")
            body.append("</ul>")
        body.append("</body></html>")
        return "".join(body)

    @app.get("/runs/{run_id}/approval-history")
    def approval_history(run_id: str):
        return ok("history", app.state.agent.get_approval_history(run_id), run_id=run_id)

    @app.get("/approvals")
    def approvals():
        return ok("pending", app.state.agent.list_pending_approvals())

    @app.post("/approvals/{run_id}/{step_id}/approve")
    @limiter.limit("20/minute")
    async def approve(request: Request, run_id: str, step_id: int, payload: ApprovalDecisionRequest):
        return await app.state.agent.approve_step(run_id, step_id, actor=payload.actor, reason=payload.reason)

    @app.post("/approvals/{run_id}/{step_id}/reject")
    @limiter.limit("20/minute")
    def reject(request: Request, run_id: str, step_id: int, payload: ApprovalDecisionRequest):
        return app.state.agent.reject_step(run_id, step_id, actor=payload.actor, reason=payload.reason)

    @app.get("/dashboard", response_class=HTMLResponse)
    def dashboard():
        console = build_console_snapshot()
        recent = app.state.agent.memory.list_recent_runs(limit=10)
        approvals = app.state.agent.list_pending_approvals()
        profile = app.state.profiles.get_capability_matrix()
        metrics_snapshot = app.state.metrics.snapshot()
        diagnostics_snapshot = app.state.metrics.diagnostics_summary()
        repo_context = app.state.agent.get_repo_context_summary()
        last_failed = app.state.agent.resume_last_failed_run()
        queue_jobs = app.state.queue.list_jobs()[:10]
        provider_health = app.state.agent.router.get_provider_health()
        provider_observability = app.state.agent.router.get_router_observability()
        git_state = app.state.agent.executor.git.inspect_repo()
        release_state = app.state.release.evaluate()

        def badge(status: str) -> str:
            return f"<span style='padding:2px 8px;border-radius:999px;border:1px solid #999'>{status}</span>"

        body = [
            "<html><body style='font-family:Arial,sans-serif;max-width:1100px;margin:24px auto;padding:0 16px'>",
            "<h1>Velocity Claw Dashboard</h1>",
            f"<p>Execution profile: <b>{app.state.settings.execution_profile}</b></p>",
            f"<p>Queue concurrency: <b>{app.state.queue.max_concurrency}</b> | Active workers: <b>{app.state.queue.active_count()}</b></p>",
            "<p>Quick links: <a href='/status'>/status</a> | <a href='/ops/console'>/ops/console</a> | <a href='/metrics'>/metrics</a> | <a href='/diagnostics'>/diagnostics</a> | <a href='/release/readiness'>/release/readiness</a> | <a href='/providers/health'>/providers/health</a> | <a href='/providers/observability'>/providers/observability</a> | <a href='/git/summary'>/git/summary</a> | <a href='/memory/context'>/memory/context</a> | <a href='/memory/resume?task=fix'>/memory/resume</a> | <a href='/runs'>/runs</a> | <a href='/approvals'>/approvals</a> | <a href='/profiles'>/profiles</a> | <a href='/queue'>/queue</a></p>",
            "<h2>Operations console</h2>",
            f"<p>Release: <b>{console['release']['readiness']}</b> ({console['release']['score']}/{console['release']['total_checks']}) | Queue running: <b>{console['queue']['running']}</b> | Queue failed: <b>{console['queue']['failed']}</b> | Approvals pending: <b>{console['approvals']['pending']}</b> | Failed routes: <b>{console['providers'].get('failed_routes', 0)}</b></p>",
        ]
        if console.get("last_failed_run"):
            body.append(f"<p>Last failed run: <code>{console['last_failed_run']['run_id']}</code> — {console['last_failed_run']['task']} — <a href='/runs/{console['last_failed_run']['run_id']}/view'>open</a></p>")
        else:
            body.append("<p>No failed runs currently recorded.</p>")
        body.extend([
            "<h2>Release readiness</h2>",
            f"<p>Status: <b>{release_state.get('readiness')}</b> | Score: <b>{release_state.get('score')}/{release_state.get('total_checks')}</b></p>",
            f"<p>Blocking issues: <b>{len(release_state.get('blocking_issues', []))}</b> | Warnings: <b>{len(release_state.get('warnings', []))}</b></p>",
            "<h2>Provider/router observability</h2>",
            f"<p>Recent routes: <b>{provider_observability.get('summary', {}).get('route_count', 0)}</b> | Fallback successes: <b>{provider_observability.get('summary', {}).get('fallback_successes', 0)}</b> | Failed routes: <b>{provider_observability.get('summary', {}).get('failed_routes', 0)}</b></p>",
            "<h2>Git summary</h2>",
            f"<p>Branch: <b>{git_state.get('branch') or ''}</b> | Clean: <b>{git_state.get('is_clean')}</b></p>",
            f"<pre>{(git_state.get('diff_stat') or '(no diff)')[:1500]}</pre>",
            "<h2>Metrics</h2>",
            "<ul>",
        ])
        for key, value in metrics_snapshot.items():
            body.append(f"<li>{key}: <b>{value}</b></li>")
        body.append("</ul>")

        body.append("<h2>Diagnostics summary</h2><ul>")
        for section, payload in diagnostics_snapshot.items():
            if isinstance(payload, dict):
                body.append(f"<li><b>{section}</b><ul>")
                for k, v in payload.items():
                    body.append(f"<li>{k}: <b>{v}</b></li>")
                body.append("</ul></li>")
            else:
                body.append(f"<li>{section}: <b>{payload}</b></li>")
        body.append("</ul>")

        body.append("<h2>Provider health</h2>")
        body.append("<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse;width:100%'>")
        body.append("<tr><th>Provider</th><th>Requests</th><th>Successes</th><th>Failures</th><th>Cooldown</th><th>Last task type</th><th>Last error</th></tr>")
        for provider, state in provider_health.items():
            body.append(f"<tr><td>{provider}</td><td>{state.get('requests', 0)}</td><td>{state.get('successes', 0)}</td><td>{state.get('failures', 0)}</td><td>{badge('yes' if state.get('in_cooldown') else 'no')}</td><td>{state.get('last_task_type') or ''}</td><td>{state.get('last_error') or ''}</td></tr>")
        body.append("</table>")

        history = provider_observability.get('recent_route_history', [])
        body.append("<h2>Recent route history</h2>")
        if history:
            body.append("<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse;width:100%'>")
            body.append("<tr><th>Task type</th><th>Status</th><th>Selected provider</th><th>Attempts</th></tr>")
            for item in history[-10:]:
                attempts = "; ".join(f"{a.get('provider')}:{a.get('status')}" for a in item.get('attempts', []))
                body.append(f"<tr><td>{item.get('task_type')}</td><td>{item.get('status')}</td><td>{item.get('selected_provider') or ''}</td><td>{attempts}</td></tr>")
            body.append("</table>")
        else:
            body.append("<p>No route history recorded yet.</p>")

        body.append("<h2>Repo context summary</h2>")
        body.append(f"<p>Project facts: <b>{len(repo_context.get('project_facts', {}))}</b> | Recent notes: <b>{len(repo_context.get('recent_notes', []))}</b> | Recent fix attempts: <b>{len(repo_context.get('recent_fix_attempts', []))}</b></p>")

        body.append("<h2>Active profile matrix</h2>")
        body.append(f"<p>{profile['description']}</p>")
        body.append("<ul>")
        for key, value in profile["capabilities"].items():
            body.append(f"<li>{key}: <b>{value}</b></li>")
        body.append("</ul>")

        body.append("<h2>Queue jobs</h2>")
        if queue_jobs:
            body.append("<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse;width:100%'>")
            body.append("<tr><th>Job ID</th><th>Task</th><th>Status</th><th>Attempts</th><th>Terminal reason</th><th>Worker Slot</th></tr>")
            for job in queue_jobs:
                body.append(f"<tr><td><code>{job['job_id']}</code></td><td>{job['task']}</td><td>{badge(job['status'])}</td><td>{job['attempts']}</td><td>{job.get('terminal_reason') or ''}</td><td>{job.get('worker_slot') or ''}</td></tr>")
            body.append("</table>")
        else:
            body.append("<p>No queue jobs recorded.</p>")

        body.append("<h2>Recent runs</h2>")
        body.append("<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse;width:100%'>")
        body.append("<tr><th>Run ID</th><th>Task</th><th>Status</th><th>Created</th><th>View</th><th>Planning context</th><th>Resume context</th><th>Forensics</th><th>Report</th></tr>")
        for run in recent:
            body.append(
                f"<tr><td><code>{run['run_id']}</code></td><td>{run['task']}</td><td>{badge(run['status'])}</td><td>{run['created_at']}</td><td><a href='/runs/{run['run_id']}/view'>open</a></td><td><a href='/runs/{run['run_id']}/planning-context'>json</a></td><td><a href='/runs/{run['run_id']}/resume-context'>json</a></td><td><a href='/runs/{run['run_id']}/forensics'>json</a></td><td><a href='/runs/{run['run_id']}/report'>json</a></td></tr>"
            )
        body.append("</table>")

        body.append("<h2>Last failed run</h2>")
        if last_failed:
            forensic = last_failed.get('forensics') or {}
            body.append(f"<p><code>{last_failed['run_id']}</code> — {last_failed['task']} — {badge(last_failed['status'])} — <a href='/runs/{last_failed['run_id']}/view'>details</a> — <a href='/runs/{last_failed['run_id']}/forensics'>forensics</a> — <a href='/runs/{last_failed['run_id']}/report'>report</a></p>")
            body.append(f"<p>Failed step: <b>{(forensic.get('failed_step') or {}).get('title') or 'n/a'}</b> | Artifacts: <b>{forensic.get('artifact_count', 0)}</b></p>")
        else:
            body.append("<p>No failed runs recorded.</p>")

        body.append("<h2>Pending approvals</h2>")
        if approvals:
            body.append("<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse;width:100%'>")
            body.append("<tr><th>Run ID</th><th>Step</th><th>Tool</th><th>Risk</th><th>Triggers</th><th>Reason</th></tr>")
            for item in approvals:
                approval_data = item.get("result") if isinstance(item.get("result"), dict) else {}
                triggers = ", ".join(approval_data.get("triggers", [])) if approval_data else ""
                reason = approval_data.get("reason") if approval_data else None
                risk_level = approval_data.get("risk_level") if approval_data else None
                body.append(
                    f"<tr><td><code>{item['run_id']}</code></td><td>{item['title']}</td><td>{item['tool']}</td><td>{risk_level or 'n/a'}</td><td>{triggers or 'n/a'}</td><td>{reason or 'n/a'}</td></tr>"
                )
            body.append("</table>")
        else:
            body.append("<p>No pending approvals.</p>")

        body.append("</body></html>")
        return "".join(body)

    return app
