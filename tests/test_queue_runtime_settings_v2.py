from pathlib import Path

from fastapi import FastAPI

from velocity_claw.api.app import install_queue_persistence_v2
from velocity_claw.core.queue import RunQueue


class QueueSettings:
    queue_max_attempts = 7
    queue_recover_on_startup = True


class FakeAgent:
    async def run_task(self, task, context=None):
        return {"status": "completed", "task": task}


class FakeLogger:
    def info(self, *args, **kwargs):
        pass


def test_production_queue_settings_apply_before_startup_scheduling(tmp_path: Path):
    db_path = tmp_path / "queue.db"
    initial = RunQueue(db_path=str(db_path), recover_on_startup=False)
    job = initial.enqueue("recover with configured runtime")
    job.status = "running"
    job.attempts = 1
    job.worker_slot = "stale-slot"
    initial._persist_job(job)

    app = FastAPI()
    app.state.settings = QueueSettings()
    app.state.queue = RunQueue(db_path=str(db_path), max_attempts=3, recover_on_startup=False)
    app.state.agent = FakeAgent()
    app.state.logger = FakeLogger()

    assert app.state.queue.get(job.job_id).status == "running"

    install_queue_persistence_v2(app)

    recovered = app.state.queue.get(job.job_id)
    assert app.state.queue.max_attempts == 7
    assert app.state.queue.recover_on_startup is True
    assert recovered.status == "queued"
    assert recovered.worker_slot is None
    assert recovered.recovery_count == 1
    assert app.state.queue.startup_recovery["recovered_running"] == 1
