from fastapi import FastAPI
from fastapi.testclient import TestClient

from velocity_claw.__version__ import __product_name__, __release_stage__, __version__
from velocity_claw.api.app import install_diagnostics_v2
from velocity_claw.api.diagnostics_v2 import build_diagnostics_v2


class FakeSettings:
    env = "production"
    execution_profile = "safe"
    safe_mode = True
    trusted_mode = False
    shell_enabled = False
    git_enabled = False
    dry_run = False


class RiskySettings(FakeSettings):
    trusted_mode = True
    shell_enabled = True
    git_enabled = True


class FakeRelease:
    def evaluate(self):
        return {
            "readiness": "warning",
            "score": 4,
            "total_checks": 5,
            "blocking_issues": [],
            "warnings": ["provider fallback active"],
        }


class FakeQueue:
    max_concurrency = 2

    def list_jobs(self):
        return [
            {"job_id": "job-1", "status": "running"},
            {"job_id": "job-2", "status": "failed"},
            {"job_id": "job-3", "status": "queued"},
        ]

    def active_count(self):
        return 1


class FakeRouter:
    def get_router_observability(self):
        return {"summary": {"route_count": 2, "failed_routes": 1}}

    def get_provider_health(self):
        return {
            "openai": {"requests": 3, "successes": 2, "failures": 1, "in_cooldown": False},
            "anthropic": {"requests": 1, "successes": 0, "failures": 1, "in_cooldown": True},
        }


class FakeAgent:
    def __init__(self):
        self.router = FakeRouter()

    def list_pending_approvals(self):
        return [{"run_id": "run-1", "step_id": 2, "reason": "patch requires review"}]

    def resume_last_failed_run(self):
        return {"run_id": "run-failed", "task": "Repair tests", "status": "failed"}


class FakeMetrics:
    def snapshot(self):
        return {"tasks_total": 2, "tasks_failed": 1, "queue_failed": 1}


class FakeAppState:
    settings = FakeSettings()
    release = FakeRelease()
    queue = FakeQueue()
    agent = FakeAgent()
    metrics = FakeMetrics()


def make_app():
    app = FastAPI()
    app.state.settings = FakeSettings()
    app.state.release = FakeRelease()
    app.state.queue = FakeQueue()
    app.state.agent = FakeAgent()
    app.state.metrics = FakeMetrics()
    install_diagnostics_v2(app)
    return app


def test_build_diagnostics_v2_summarizes_runtime_state_flags_and_version():
    result = build_diagnostics_v2(
        settings=RiskySettings(),
        release_state=FakeRelease().evaluate(),
        queue_jobs=FakeQueue().list_jobs(),
        approvals=FakeAgent().list_pending_approvals(),
        provider_observability=FakeRouter().get_router_observability(),
        provider_health=FakeRouter().get_provider_health(),
        last_failed=FakeAgent().resume_last_failed_run(),
        metrics=FakeMetrics().snapshot(),
        active_workers=1,
        max_concurrency=2,
    )

    assert result["status"] == "ok"
    assert result["version"]["product"] == __product_name__
    assert result["version"]["version"] == __version__
    assert result["version"]["release_stage"] == __release_stage__
    assert result["summary"]["queue_total"] == 3
    assert result["summary"]["queue_failed"] == 1
    assert result["summary"]["approvals_pending"] == 1
    assert result["summary"]["provider_failures"] == 2
    assert result["summary"]["provider_cooldowns"] == 1
    assert result["runtime"]["execution_profile"] == "safe"
    assert result["links"]["version"] == "/version"
    codes = {flag["code"] for flag in result["risk_flags"]}
    assert "trusted_mode_enabled" in codes
    assert "shell_enabled" in codes
    assert "git_enabled" in codes
    assert "release_not_ready" in codes
    assert "queue_failures" in codes
    assert "pending_approvals" in codes
    assert "provider_cooldown" in codes
    assert "last_failed_run" in codes


def test_diagnostics_v2_endpoint_returns_operational_snapshot():
    client = TestClient(make_app())

    response = client.get("/diagnostics/v2")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["version"]["version"] == __version__
    assert payload["summary"]["release_readiness"] == "warning"
    assert payload["queue"]["running"] == 1
    assert payload["queue"]["failed"] == 1
    assert payload["approvals"]["pending"] == 1
    assert payload["providers"]["summary"]["in_cooldown"] == 1
    assert payload["last_failed_run"]["run_id"] == "run-failed"
    assert payload["links"]["dashboard_v2"] == "/dashboard/v2"
    assert payload["links"]["version"] == "/version"
