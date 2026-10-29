import asyncio
import sqlite3
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from velocity_claw.api.app import install_queue_persistence_v2
from velocity_claw.api.server import create_app, limiter
from velocity_claw.config.settings import Settings
from velocity_claw.core.external_worker import ExternalQueueWorker
from velocity_claw.core.queue import RunQueue


class FakeAgent:
    def __init__(self):
        self.calls = []

    async def run_task(self, task, context=None):
        self.calls.append((task, context))
        return {
            "run_id": "run-worker",
            "task": task,
            "status": "completed",
            "summary": "done",
            "steps": [],
            "signature": "velocity claw",
        }


class FakeLogger:
    def info(self, *args, **kwargs):
        return None

    def warning(self, *args, **kwargs):
        return None


def test_queue_schema_adds_external_worker_lease_columns(tmp_path: Path):
    db_path = tmp_path / "queue.db"

    RunQueue(db_path=str(db_path))

    with sqlite3.connect(db_path) as conn:
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(queue_jobs)").fetchall()
        }
        control = conn.execute(
            "SELECT value FROM queue_control WHERE key = 'accepting_work'"
        ).fetchone()

    assert {"lease_expires_at", "heartbeat_at"}.issubset(columns)
    assert control == ("true",)


def test_claim_fields_round_trip_through_sqlite(tmp_path: Path):
    db_path = tmp_path / "queue.db"
    queue = RunQueue(db_path=str(db_path), max_attempts=3)
    queued = queue.enqueue("round trip", {"source": "sqlite"})

    claimed = queue.claim_next("worker-round-trip", lease_seconds=30)
    restored = RunQueue(db_path=str(db_path)).get(queued.job_id)

    assert claimed is not None
    assert restored is not None
    assert restored.job_id == queued.job_id
    assert restored.task == "round trip"
    assert restored.context == {"source": "sqlite"}
    assert restored.status == "running"
    assert restored.attempts == 1
    assert restored.worker_slot == "worker-round-trip"
    assert restored.heartbeat_at is not None
    assert restored.lease_expires_at is not None


def test_two_workers_cannot_claim_the_same_job(tmp_path: Path):
    db_path = tmp_path / "queue.db"
    first = RunQueue(db_path=str(db_path), max_attempts=3)
    second = RunQueue(db_path=str(db_path), max_attempts=3)
    queued = first.enqueue("atomic claim", {"source": "test"})

    claimed = first.claim_next("worker-a", lease_seconds=30)
    duplicate = second.claim_next("worker-b", lease_seconds=30)

    assert claimed is not None
    assert claimed.job_id == queued.job_id
    assert claimed.worker_slot == "worker-a"
    assert claimed.attempts == 1
    assert duplicate is None


def test_expired_claim_is_recovered_and_reclaimed(tmp_path: Path):
    db_path = tmp_path / "queue.db"
    first = RunQueue(db_path=str(db_path), max_attempts=3)
    second = RunQueue(db_path=str(db_path), max_attempts=3)
    queued = first.enqueue("recover lease")
    stale = first.claim_next("worker-a", lease_seconds=30)
    stale.lease_expires_at = "2000-01-01T00:00:00+00:00"
    first._persist_job(stale)

    reclaimed = second.claim_next("worker-b", lease_seconds=30)

    assert reclaimed is not None
    assert reclaimed.job_id == queued.job_id
    assert reclaimed.worker_slot == "worker-b"
    assert reclaimed.attempts == 2
    assert reclaimed.recovery_count == 1
    assert any(
        event["reason"] == "external_worker_lease_expired"
        for event in reclaimed.history
    )


def test_cancelled_external_job_rejects_late_worker_result(tmp_path: Path):
    db_path = tmp_path / "queue.db"
    worker_queue = RunQueue(db_path=str(db_path), max_attempts=3)
    api_queue = RunQueue(db_path=str(db_path), max_attempts=3)
    api_queue.configure_execution_mode("external")
    job = worker_queue.enqueue("cancel me")
    worker_queue.claim_next("worker-a", lease_seconds=30)

    cancelled = api_queue.cancel(job.job_id)
    late = worker_queue.finish_claim(
        job.job_id,
        "worker-a",
        result={"status": "completed"},
    )

    assert cancelled.status == "cancelled"
    assert late.status == "cancelled"
    assert late.result is None
    assert late.worker_slot is None


def test_persistent_pause_blocks_claims_until_resume(tmp_path: Path):
    db_path = tmp_path / "queue.db"
    api_queue = RunQueue(db_path=str(db_path))
    api_queue.configure_execution_mode("external")
    worker_queue = RunQueue(db_path=str(db_path))
    api_queue.enqueue("paused")

    api_queue.pause()
    assert worker_queue.claim_next("worker-a", lease_seconds=30) is None

    api_queue.resume()
    assert worker_queue.claim_next("worker-a", lease_seconds=30) is not None


def test_external_mode_rejects_embedded_execution_paths(tmp_path: Path):
    async def scenario():
        queue = RunQueue(db_path=str(tmp_path / "queue.db"))
        queue.configure_execution_mode("external")
        job = queue.enqueue("external only")
        calls = []

        async def runner(task, context=None):
            calls.append((task, context))
            return {"status": "completed"}

        assert queue.schedule(job.job_id, runner) is False
        assert queue.schedule_pending(runner) == []
        assert queue.resume(runner) == []
        assert await queue.run_job(job.job_id, runner) == job
        assert calls == []
        assert queue.get(job.job_id).status == "queued"

    asyncio.run(scenario())


def test_external_worker_run_once_executes_and_persists_result(tmp_path: Path):
    async def scenario():
        settings = Settings(
            env="test",
            memory_db_path=str(tmp_path / "memory.db"),
            queue_execution_mode="external",
            queue_worker_lease_seconds=30,
        )
        queue = RunQueue(
            db_path=f"{settings.memory_db_path}.queue",
            max_attempts=3,
        )
        job = queue.enqueue("worker task", {"answer": 42})
        agent = FakeAgent()
        worker = ExternalQueueWorker(
            settings,
            agent=agent,
            queue=queue,
            worker_id="worker-test",
        )

        assert await worker.run_once() is True
        restored = RunQueue(db_path=f"{settings.memory_db_path}.queue").get(job.job_id)

        assert agent.calls == [("worker task", {"answer": 42})]
        assert restored.status == "completed"
        assert restored.worker_slot is None
        assert restored.lease_expires_at is None
        assert restored.result["run_id"] == "run-worker"

    asyncio.run(scenario())


def test_external_worker_settings_use_prefixed_environment(monkeypatch):
    monkeypatch.setenv("VELOCITY_CLAW_ENV", "test")
    monkeypatch.setenv("VELOCITY_CLAW_QUEUE_EXECUTION_MODE", "external")
    monkeypatch.setenv("VELOCITY_CLAW_QUEUE_WORKER_POLL_MS", "125")
    monkeypatch.setenv("VELOCITY_CLAW_QUEUE_WORKER_LEASE_SECONDS", "45")

    settings = Settings()

    assert settings.queue_execution_mode == "external"
    assert settings.queue_worker_poll_ms == 125
    assert settings.queue_worker_lease_seconds == 45


def test_api_external_mode_only_enqueues_until_worker_claims(tmp_path: Path):
    settings = Settings(
        env="test",
        memory_db_path=str(tmp_path / "memory.db"),
        workspace_root=str(tmp_path),
        queue_execution_mode="external",
        queue_worker_lease_seconds=30,
    )
    with patch("velocity_claw.api.server.load_settings", return_value=settings):
        app = create_app()
    limiter.enabled = False

    try:
        with TestClient(app, client=("127.0.0.42", 50001)) as client:
            submitted = client.post(
                "/queue/submit",
                json={"task": "external API job", "context": {"source": "api"}},
            )
            payload = submitted.json()["job"]

            assert submitted.status_code == 200
            assert payload["status"] == "queued"
            assert payload["scheduled"] is False
            assert payload["execution_mode"] == "external"
            assert app.state.queue.active_count() == 0

            agent = FakeAgent()
            worker = ExternalQueueWorker(
                settings,
                agent=agent,
                queue=RunQueue(
                    db_path=f"{settings.memory_db_path}.queue",
                    max_attempts=settings.queue_max_attempts,
                ),
                worker_id="api-worker",
            )
            assert asyncio.run(worker.run_once()) is True

            status = client.get(f"/queue/{payload['job_id']}").json()["job"]
            assert status["status"] == "completed"
            assert agent.calls == [("external API job", {"source": "api"})]
    finally:
        limiter.enabled = True

    asyncio.run(app.state.agent.close())


def test_production_queue_startup_does_not_schedule_in_external_mode(tmp_path: Path):
    settings = Settings(
        env="test",
        memory_db_path=str(tmp_path / "memory.db"),
        queue_execution_mode="external",
    )
    app = FastAPI()
    app.state.settings = settings
    app.state.queue = RunQueue(db_path=f"{settings.memory_db_path}.queue")
    app.state.agent = FakeAgent()
    app.state.logger = FakeLogger()
    job = app.state.queue.enqueue("wait for worker")

    install_queue_persistence_v2(app)

    with TestClient(app):
        assert app.state.agent.calls == []
        assert app.state.queue.get(job.job_id).status == "queued"
        assert app.state.queue.runtime_summary()["execution_mode"] == "external"


def test_external_worker_deployment_templates_are_opt_in_and_hardened():
    service = Path("deploy/systemd/velocity-claw-worker.service").read_text(
        encoding="utf-8"
    )
    compose = Path("deploy/docker/docker-compose.yml").read_text(encoding="utf-8")
    installer = Path("deploy/install/install.sh").read_text(encoding="utf-8")

    assert "cli.py --worker" in service
    assert "User=velocityclaw" in service
    assert "NoNewPrivileges=true" in service
    assert "ProtectSystem=full" in service
    assert 'profiles: ["worker"]' in compose
    assert 'command: ["python", "cli.py", "--worker"]' in compose
    assert "velocity-claw-worker.service" in installer
    assert 'systemctl enable "$WORKER_SERVICE_NAME"' not in installer
