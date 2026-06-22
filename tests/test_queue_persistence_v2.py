import asyncio
import sqlite3
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from velocity_claw.api.app import install_queue_persistence_v2
from velocity_claw.core.queue import RunQueue


async def wait_for(predicate, timeout=1.0):
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if predicate():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("condition was not reached before timeout")


def test_queue_schema_migrates_existing_database(tmp_path: Path):
    db_path = tmp_path / "queue.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE queue_jobs (
                job_id TEXT PRIMARY KEY,
                task TEXT NOT NULL,
                context TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                result TEXT,
                error TEXT,
                attempts INTEGER NOT NULL DEFAULT 0,
                worker_slot TEXT,
                terminal_reason TEXT,
                last_attempt_started_at TEXT,
                history TEXT
            )
            """
        )

    RunQueue(db_path=str(db_path))

    with sqlite3.connect(db_path) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(queue_jobs)").fetchall()}

    assert "recovery_count" in columns
    assert "last_recovered_at" in columns
    assert "scheduled_at" in columns


def test_running_job_is_recovered_to_queued_after_restart(tmp_path: Path):
    db_path = tmp_path / "queue.db"
    first = RunQueue(db_path=str(db_path))
    job = first.enqueue("recover me")
    job.status = "running"
    job.attempts = 1
    job.worker_slot = "slot-1"
    job.scheduled_at = "2026-06-22T00:00:00"
    first._persist_job(job)

    recovered_queue = RunQueue(db_path=str(db_path), recover_on_startup=True)
    recovered = recovered_queue.get(job.job_id)

    assert recovered.status == "queued"
    assert recovered.worker_slot is None
    assert recovered.scheduled_at is None
    assert recovered.recovery_count == 1
    assert recovered.last_recovered_at is not None
    assert recovered.history[-1]["reason"] == "recovered_after_restart_from_running"
    assert recovered_queue.startup_recovery["recovered_running"] == 1
    assert recovered_queue.startup_recovery["queued_available"] == 1


def test_persisted_queued_job_is_scheduled_once(tmp_path: Path):
    db_path = tmp_path / "queue.db"
    first = RunQueue(db_path=str(db_path))
    job = first.enqueue("queued task", {"source": "restart"})
    queue = RunQueue(db_path=str(db_path))
    calls = []

    async def runner(task, context):
        calls.append((task, context))
        return {"status": "completed", "task": task}

    async def scenario():
        scheduled = queue.schedule_pending(runner)
        duplicate = queue.schedule(job.job_id, runner)
        assert scheduled == [job.job_id]
        assert duplicate is False
        await wait_for(lambda: queue.get(job.job_id).status == "completed")
        await wait_for(lambda: queue.scheduled_count() == 0)

    asyncio.run(scenario())

    restored = RunQueue(db_path=str(db_path))
    completed = restored.get(job.job_id)
    assert completed.status == "completed"
    assert completed.attempts == 1
    assert completed.terminal_reason == "runner_completed"
    assert calls == [("queued task", {"source": "restart"})]


def test_cancelled_running_job_is_not_overwritten_by_runner_result():
    queue = RunQueue(max_concurrency=1)
    job = queue.enqueue("long task")

    async def scenario():
        started = asyncio.Event()
        release = asyncio.Event()

        async def runner(task, context):
            started.set()
            await release.wait()
            return {"status": "completed"}

        assert queue.schedule(job.job_id, runner) is True
        await started.wait()
        cancelled = queue.cancel(job.job_id)
        assert cancelled.status == "cancelled"
        release.set()
        await wait_for(lambda: queue.scheduled_count() == 0)

    asyncio.run(scenario())

    final = queue.get(job.job_id)
    assert final.status == "cancelled"
    assert final.result is None
    assert final.terminal_reason == "cancelled_by_operator"
    assert any(event["reason"] == "runner_result_discarded_after_cancel" for event in final.history)


def test_requeue_blocks_exhausted_attempts_unless_forced():
    queue = RunQueue(max_attempts=1)
    job = queue.enqueue("retry task")
    job.status = "failed"
    job.attempts = 1
    job.terminal_reason = "runner_exception"

    blocked = queue.requeue(job.job_id)
    assert blocked.status == "failed"
    assert blocked.terminal_reason == "max_attempts_exhausted"

    forced = queue.requeue(job.job_id, force=True)
    assert forced.status == "queued"
    assert forced.terminal_reason is None
    assert forced.error is None


class FakeAgent:
    def __init__(self):
        self.calls = []

    async def run_task(self, task, context=None):
        self.calls.append((task, context))
        return {"run_id": "run-1", "task": task, "status": "completed", "summary": "ok", "steps": [], "signature": "velocity claw"}


class FakeLogger:
    def info(self, *args, **kwargs):
        pass


def test_queue_v2_runtime_and_recovery_endpoints(tmp_path: Path):
    app = FastAPI()
    app.state.queue = RunQueue(db_path=str(tmp_path / "queue.db"))
    app.state.agent = FakeAgent()
    app.state.logger = FakeLogger()
    job = app.state.queue.enqueue("api recovery")
    install_queue_persistence_v2(app)

    with TestClient(app) as client:
        runtime = client.get("/queue/v2/runtime")
        assert runtime.status_code == 200
        assert runtime.json()["queue"]["persistence_enabled"] is True

        recover = client.post("/queue/v2/recover")
        assert recover.status_code == 200
        assert recover.json()["status"] == "ok"

        async def wait_completed():
            await wait_for(lambda: app.state.queue.get(job.job_id).status == "completed")

        asyncio.run(wait_completed())

    assert app.state.agent.calls == [("api recovery", None)]


def test_queue_v2_requeue_schedules_failed_job(tmp_path: Path):
    app = FastAPI()
    app.state.queue = RunQueue(db_path=str(tmp_path / "queue.db"), max_attempts=3)
    app.state.agent = FakeAgent()
    app.state.logger = FakeLogger()
    job = app.state.queue.enqueue("retry through api")
    job.status = "failed"
    job.attempts = 1
    job.error = "temporary failure"
    job.terminal_reason = "runner_exception"
    app.state.queue._persist_job(job)
    install_queue_persistence_v2(app)

    with TestClient(app) as client:
        response = client.post(f"/queue/v2/{job.job_id}/requeue")
        assert response.status_code == 200
        assert response.json()["scheduled"] is True

    assert app.state.queue.get(job.job_id).status == "completed"
    assert app.state.agent.calls == [("retry through api", None)]
