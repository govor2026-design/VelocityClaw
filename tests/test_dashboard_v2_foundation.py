from fastapi import FastAPI
from fastapi.testclient import TestClient

from velocity_claw.api.app import install_dashboard_v2
from velocity_claw.api.dashboard_v2 import approval_links, render_dashboard_v2, run_links


class FakeSettings:
    execution_profile = "safe"
    safe_mode = True
    trusted_mode = False


class FakeMetrics:
    def __init__(self):
        self.values = {}

    def set_value(self, key, value):
        self.values[key] = value

    def snapshot(self):
        return dict(self.values)


class FakeQueue:
    max_concurrency = 2

    def list_jobs(self):
        return [
            {
                "job_id": "job-1",
                "task": "Run tests",
                "status": "running",
                "attempts": 1,
                "terminal_reason": None,
            }
        ]

    def active_count(self):
        return 1


class FakeMemory:
    def list_recent_runs(self, limit=10):
        return [
            {
                "run_id": "run-1",
                "task": "Analyze repo",
                "status": "completed",
                "created_at": "2026-05-11T00:00:00Z",
            }
        ]


class FakeRouter:
    def get_router_observability(self):
        return {
            "summary": {
                "route_count": 3,
                "fallback_successes": 1,
                "failed_routes": 0,
            },
            "recent_route_history": [],
        }

    def get_provider_health(self):
        return {
            "openai": {
                "requests": 2,
                "successes": 2,
                "failures": 0,
                "in_cooldown": False,
                "last_error": None,
            }
        }


class FakeAgent:
    def __init__(self):
        self.memory = FakeMemory()
        self.router = FakeRouter()

    def list_pending_approvals(self):
        return [
            {
                "run_id": "run-2",
                "step_id": 3,
                "title": "Apply patch",
                "reason": "patch requires review",
            }
        ]

    def resume_last_failed_run(self):
        return {
            "run_id": "run-failed",
            "task": "Repair tests",
            "status": "failed",
        }


class FakeRelease:
    def evaluate(self):
        return {
            "readiness": "ready",
            "score": 5,
            "total_checks": 5,
            "blocking_issues": [],
            "warnings": [],
        }


def make_fake_app():
    app = FastAPI()
    app.state.settings = FakeSettings()
    app.state.metrics = FakeMetrics()
    app.state.queue = FakeQueue()
    app.state.agent = FakeAgent()
    app.state.release = FakeRelease()
    install_dashboard_v2(app)
    return app


def test_run_links_include_v2_and_classic_destinations():
    html = run_links("run-1")

    assert "/runs/run-1/detail/v2" in html
    assert "/runs/run-1/artifacts/v2" in html
    assert "/runs/run-1/forensics" in html
    assert "/runs/run-1/report" in html
    assert "/runs/run-1/view" in html


def test_approval_links_include_review_and_run_detail():
    html = approval_links("run-2", 3)

    assert "/approvals/v2/run-2/3" in html
    assert "/runs/run-2/detail/v2" in html


def test_render_dashboard_v2_contains_core_sections_links_and_escapes_values():
    html = render_dashboard_v2(
        execution_profile="safe<script>",
        safe_mode=True,
        trusted_mode=False,
        release_state={"readiness": "ready", "score": 1, "total_checks": 1},
        console={"queue": {"running": 0, "failed": 0}, "approvals": {"pending": 1}},
        recent_runs=[{"run_id": "run-1", "task": "Fix <bug>", "status": "completed", "created_at": "now"}],
        approvals=[{"run_id": "run-2", "step_id": 3, "title": "Apply patch", "reason": "review"}],
        queue_jobs=[],
        metrics={"tasks_total": 1},
        provider_observability={"summary": {"failed_routes": 0}},
        provider_health={},
        last_failed={"run_id": "run-failed", "task": "Repair tests", "status": "failed"},
    )

    assert "Velocity Claw Dashboard v2" in html
    assert "Recent runs" in html
    assert "Pending approvals" in html
    assert "Provider health" in html
    assert "safe&lt;script&gt;" in html
    assert "Fix &lt;bug&gt;" in html
    assert "/runs/run-1/detail/v2" in html
    assert "/runs/run-1/artifacts/v2" in html
    assert "/approvals/v2/run-2/3" in html
    assert "/runs/run-failed/detail/v2" in html


def test_dashboard_v2_endpoint_renders_operational_snapshot():
    client = TestClient(make_fake_app())
    response = client.get("/dashboard/v2")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Velocity Claw Dashboard v2" in response.text
    assert "Analyze repo" in response.text
    assert "Apply patch" in response.text
    assert "Repair tests" in response.text
    assert "openai" in response.text
    assert "/runs/run-1/detail/v2" in response.text
    assert "/approvals/v2/run-2/3" in response.text
