from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from velocity_claw.api.app import install_dashboard_v2
from velocity_claw.api.dashboard_v2 import render_dashboard_v2, render_run_inspector_v2
from velocity_claw.memory.run_profiles import install_run_profile_tracking
from velocity_claw.memory.store import MemoryStore


class MemorySettings:
    memory_enabled = True
    memory_retention_days = 30
    memory_retention_min_runs = 10
    memory_cleanup_vacuum = False

    def __init__(self, db_path: Path):
        self.memory_db_path = str(db_path)


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
        return []

    def active_count(self):
        return 0


class FakeRelease:
    def evaluate(self):
        return {
            "readiness": "ready",
            "score": 3,
            "total_checks": 3,
            "blocking_issues": [],
            "warnings": [],
        }


class FakeRouter:
    def get_router_observability(self):
        return {"summary": {"failed_routes": 0}}

    def get_provider_health(self):
        return {}


class FakeAgent:
    def __init__(self, memory, settings):
        self.memory = memory
        self.settings = settings
        self.router = FakeRouter()

    def list_pending_approvals(self):
        return []

    def resume_last_failed_run(self):
        return self.memory.get_last_failed_run()


def build_memory(tmp_path: Path) -> MemoryStore:
    return MemoryStore(MemorySettings(tmp_path / "memory.db"))


def test_run_profile_tracking_records_new_runs_and_marks_legacy_unknown(tmp_path: Path):
    memory = build_memory(tmp_path)
    legacy_run = memory.create_run("legacy run")
    memory.update_run_status(legacy_run, "completed")
    settings = SimpleNamespace(execution_profile="dev")
    agent = SimpleNamespace(memory=memory, settings=settings)

    store = install_run_profile_tracking(agent)
    dev_run = memory.create_run("developer run")
    memory.update_run_status(dev_run, "completed")
    settings.execution_profile = "safe"
    safe_run = memory.create_run("safe run")
    memory.update_run_status(safe_run, "completed")

    profiles = {item["run_id"]: item["execution_profile"] for item in memory.list_recent_runs(limit=10)}
    assert profiles[legacy_run] == "unknown"
    assert profiles[dev_run] == "dev"
    assert profiles[safe_run] == "safe"
    assert memory.load_run(dev_run)["execution_profile"] == "dev"
    assert store.list_profiles() == ["dev", "safe"]
    assert install_run_profile_tracking(agent) is store


def test_dashboard_renderer_exposes_filters_profile_and_inspector_link():
    html = render_dashboard_v2(
        execution_profile="safe",
        safe_mode=True,
        trusted_mode=False,
        release_state={"readiness": "ready", "score": 1, "total_checks": 1},
        console={"queue": {}, "approvals": {}},
        recent_runs=[
            {
                "run_id": "run-1",
                "task": "<script>alert(1)</script>",
                "status": "completed",
                "execution_profile": "safe",
                "created_at": "2026-06-22",
            }
        ],
        approvals=[],
        queue_jobs=[],
        metrics={},
        provider_observability={"summary": {}},
        provider_health={},
        last_failed=None,
        filters={"status": "completed", "profile": "safe", "q": "run"},
        available_statuses=["completed", "failed"],
        available_profiles=["dev", "safe", "unknown"],
        total_run_count=7,
    )

    assert "name='status'" in html
    assert "name='profile'" in html
    assert "Showing 1 of 7 recent runs" in html
    assert "/runs/run-1/inspect/v2" in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<script>alert(1)</script>" not in html
    assert "<option value='safe' selected>" in html


def test_run_inspector_filters_artifacts_and_escapes_content():
    run = {
        "run_id": "run-2",
        "task": "Inspect artifacts",
        "status": "failed",
        "execution_profile": "dev",
        "created_at": "2026-06-22",
        "steps": [
            {
                "id": 1,
                "title": "Run tests",
                "tool": "test.run",
                "args": {"command": "pytest -q"},
                "status": "failed",
                "result": {"exit_code": 1},
                "error": "failure",
            }
        ],
        "artifacts": [
            {
                "step_id": 1,
                "name": "test log",
                "artifact_type": "log",
                "content": "<script>bad()</script>",
                "created_at": "2026-06-22",
            },
            {
                "step_id": 1,
                "name": "patch",
                "artifact_type": "diff",
                "content": "+ fixed",
                "created_at": "2026-06-22",
            },
        ],
        "report": {"executive_summary": "Tests failed."},
        "forensics": {"step_count": 1, "artifact_count": 2},
    }

    html = render_run_inspector_v2(run, selected_step_id=1, artifact_type="log")

    assert "Step 1: Run tests" in html
    assert "test log" in html
    assert "patch" not in html
    assert "&lt;script&gt;bad()&lt;/script&gt;" in html
    assert "<script>bad()</script>" not in html
    assert "pytest -q" in html


def test_dashboard_routes_filter_runs_and_render_inspector(tmp_path: Path):
    memory = build_memory(tmp_path)
    settings = SimpleNamespace(execution_profile="dev", safe_mode=True, trusted_mode=False)
    agent = FakeAgent(memory, settings)
    app = FastAPI()
    app.state.settings = settings
    app.state.agent = agent
    app.state.metrics = FakeMetrics()
    app.state.queue = FakeQueue()
    app.state.release = FakeRelease()
    install_dashboard_v2(app)

    dev_run = memory.create_run("Queue worker inspection")
    memory.save_step(
        dev_run,
        {
            "id": 1,
            "title": "Inspect queue",
            "tool": "fs.read",
            "args": {"path": "velocity_claw/core/queue.py"},
            "status": "success",
            "result": {"content": "ok"},
        },
    )
    memory.save_artifact(dev_run, "queue log", "safe content", step_id=1, artifact_type="log")
    memory.update_run_status(dev_run, "completed")

    settings.execution_profile = "safe"
    safe_run = memory.create_run("Dashboard typography")
    memory.update_run_status(safe_run, "completed")

    with TestClient(app) as client:
        filtered = client.get("/dashboard/v2?profile=dev&q=queue&status=completed")
        assert filtered.status_code == 200
        assert "Queue worker inspection" in filtered.text
        assert "Dashboard typography" not in filtered.text
        assert "Filters are active" in filtered.text

        inspector = client.get(f"/runs/{dev_run}/inspect/v2?step=1&artifact_type=log")
        assert inspector.status_code == 200
        assert "Inspect queue" in inspector.text
        assert "queue log" in inspector.text
        assert "velocity_claw/core/queue.py" in inspector.text

        missing = client.get("/runs/not-found/inspect/v2")
        assert missing.status_code == 404
