import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from velocity_claw.api.app import install_queue_persistence_v2
from velocity_claw.core.queue import RunQueue


class FakeAgent:
    def __init__(self):
        self.calls = []

    async def run_task(self, task, context=None):
        self.calls.append((task, context))
        return {"status": "completed", "task": task}


class FakeLogger:
    def info(self, *args, **kwargs):
        pass


def wait_for(predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("condition was not reached before timeout")


def test_force_requeue_starts_new_retry_cycle_and_runs(tmp_path: Path):
    app = FastAPI()
    app.state.queue = RunQueue(db_path=str(tmp_path / "queue.db"), max_attempts=1)
    app.state.agent = FakeAgent()
    app.state.logger = FakeLogger()

    job = app.state.queue.enqueue("forced retry")
    job.status = "failed"
    job.attempts = 1
    job.error = "previous failure"
    job.terminal_reason = "max_attempts_exhausted"
    app.state.queue._persist_job(job)

    install_queue_persistence_v2(app)

    with TestClient(app) as client:
        response = client.post(f"/queue/v2/{job.job_id}/requeue?force=true")
        assert response.status_code == 200
        assert response.json()["scheduled"] is True
        wait_for(lambda: app.state.queue.get(job.job_id).status == "completed")
        wait_for(lambda: app.state.queue.scheduled_count() == 0)

    completed = app.state.queue.get(job.job_id)
    assert completed.status == "completed"
    assert completed.attempts == 1
    assert app.state.agent.calls == [("forced retry", None)]
    reset_events = [event for event in completed.history if event.get("reason") == "forced_retry_cycle_reset"]
    assert len(reset_events) == 1
    assert reset_events[0]["previous_attempts"] == 1
