import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from velocity_claw.api.app import install_queue_persistence_v2
from velocity_claw.core.queue import RunQueue


class QueueSettings:
    queue_max_concurrency = 1
    queue_max_attempts = 3
    queue_recover_on_startup = False
    queue_shutdown_timeout_seconds = 1


class FakeAgent:
    def __init__(self):
        self.calls = []

    async def run_task(self, task, context=None):
        self.calls.append((task, context))
        return {"status": "completed", "task": task}


class FakeLogger:
    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass


def wait_for(predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("condition was not reached before timeout")


def build_app(tmp_path: Path):
    app = FastAPI()
    app.state.settings = QueueSettings()
    app.state.queue = RunQueue(db_path=str(tmp_path / "queue.db"), max_concurrency=3)
    app.state.agent = FakeAgent()
    app.state.logger = FakeLogger()
    install_queue_persistence_v2(app)
    return app


def test_queue_runtime_exposes_orchestrator_state(tmp_path: Path):
    app = build_app(tmp_path)

    with TestClient(app) as client:
        response = client.get("/queue/v2/runtime")
        assert response.status_code == 200
        runtime = response.json()["queue"]

        assert runtime["orchestrator"] == "v2"
        assert runtime["accepting_work"] is True
        assert runtime["max_concurrency"] == 1
        assert runtime["tracked_tasks"] == 0
        assert runtime["active_slots"] == {}


def test_pause_and_resume_control_queue_scheduling(tmp_path: Path):
    app = build_app(tmp_path)

    with TestClient(app) as client:
        paused = client.post("/queue/v2/pause")
        assert paused.status_code == 200
        assert paused.json()["queue"]["accepting_work"] is False

        job = app.state.queue.enqueue("resume-me")
        recover = client.post("/queue/v2/recover")
        assert recover.status_code == 200
        assert recover.json()["scheduled_count"] == 0
        assert app.state.queue.get(job.job_id).status == "queued"

        resumed = client.post("/queue/v2/resume")
        assert resumed.status_code == 200
        assert resumed.json()["scheduled_job_ids"] == [job.job_id]
        wait_for(lambda: app.state.queue.get(job.job_id).status == "completed")
        assert app.state.agent.calls == [("resume-me", None)]


def test_drain_endpoint_validates_timeout_and_pauses_queue(tmp_path: Path):
    app = build_app(tmp_path)

    with TestClient(app) as client:
        invalid = client.post("/queue/v2/drain?timeout_seconds=-1")
        assert invalid.status_code == 400

        drained = client.post("/queue/v2/drain?timeout_seconds=0")
        assert drained.status_code == 200
        assert drained.json()["status"] == "drained"
        assert drained.json()["queue"]["accepting_work"] is False
