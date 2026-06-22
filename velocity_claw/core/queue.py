from __future__ import annotations

import asyncio
import json
import sqlite3
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Optional


TERMINAL_STATUSES = {"completed", "failed", "cancelled"}
PERSISTED_STATUSES = {"queued", "running", *TERMINAL_STATUSES}
Runner = Callable[[str, Optional[dict]], Awaitable[dict]]


def _now() -> str:
    return datetime.now().isoformat()


def _load_json(value: Optional[str], default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return default


@dataclass
class QueueJob:
    job_id: str
    task: str
    context: Optional[dict] = None
    status: str = "queued"
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    result: Optional[dict] = None
    error: Optional[str] = None
    attempts: int = 0
    worker_slot: Optional[str] = None
    terminal_reason: Optional[str] = None
    last_attempt_started_at: Optional[str] = None
    history: list[dict] = field(default_factory=list)
    recovery_count: int = 0
    last_recovered_at: Optional[str] = None
    scheduled_at: Optional[str] = None


class RunQueue:
    def __init__(
        self,
        db_path: Optional[str] = None,
        max_concurrency: int = 1,
        max_attempts: int = 3,
        recover_on_startup: bool = True,
    ):
        self.jobs: Dict[str, QueueJob] = {}
        self.db_path = db_path
        self.max_concurrency = max(1, int(max_concurrency))
        self.max_attempts = max(1, int(max_attempts))
        self.recover_on_startup = bool(recover_on_startup)
        self._semaphore = asyncio.Semaphore(self.max_concurrency)
        self._active_jobs: set[str] = set()
        self._scheduled_jobs: set[str] = set()
        self.startup_recovery: dict[str, Any] = {
            "enabled": self.recover_on_startup,
            "recovered_running": 0,
            "queued_available": 0,
            "invalid_failed": 0,
            "at": None,
        }
        if self.db_path:
            self._ensure_tables()
            self._load_jobs_from_db()
            self.startup_recovery = self._recover_loaded_jobs()

    def _ensure_tables(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS queue_jobs (
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
                    history TEXT,
                    recovery_count INTEGER NOT NULL DEFAULT 0,
                    last_recovered_at TEXT,
                    scheduled_at TEXT
                )
                """
            )
            existing = {row[1] for row in conn.execute("PRAGMA table_info(queue_jobs)").fetchall()}
            migrations = {
                "recovery_count": "INTEGER NOT NULL DEFAULT 0",
                "last_recovered_at": "TEXT",
                "scheduled_at": "TEXT",
            }
            for column, definition in migrations.items():
                if column not in existing:
                    conn.execute(f"ALTER TABLE queue_jobs ADD COLUMN {column} {definition}")

    def _load_jobs_from_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT job_id, task, context, status, created_at, updated_at,
                       result, error, attempts, worker_slot, terminal_reason,
                       last_attempt_started_at, history, recovery_count,
                       last_recovered_at, scheduled_at
                FROM queue_jobs
                """
            ).fetchall()
        for row in rows:
            self.jobs[row[0]] = QueueJob(
                job_id=row[0],
                task=row[1],
                context=_load_json(row[2], None),
                status=row[3],
                created_at=row[4],
                updated_at=row[5],
                result=_load_json(row[6], None),
                error=row[7],
                attempts=row[8] or 0,
                worker_slot=row[9],
                terminal_reason=row[10],
                last_attempt_started_at=row[11],
                history=_load_json(row[12], []),
                recovery_count=row[13] or 0,
                last_recovered_at=row[14],
                scheduled_at=row[15],
            )

    def _persist_job(self, job: QueueJob) -> None:
        if not self.db_path:
            return
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO queue_jobs (
                    job_id, task, context, status, created_at, updated_at,
                    result, error, attempts, worker_slot, terminal_reason,
                    last_attempt_started_at, history, recovery_count,
                    last_recovered_at, scheduled_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    task = excluded.task,
                    context = excluded.context,
                    status = excluded.status,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at,
                    result = excluded.result,
                    error = excluded.error,
                    attempts = excluded.attempts,
                    worker_slot = excluded.worker_slot,
                    terminal_reason = excluded.terminal_reason,
                    last_attempt_started_at = excluded.last_attempt_started_at,
                    history = excluded.history,
                    recovery_count = excluded.recovery_count,
                    last_recovered_at = excluded.last_recovered_at,
                    scheduled_at = excluded.scheduled_at
                """,
                (
                    job.job_id,
                    job.task,
                    json.dumps(job.context, ensure_ascii=False) if job.context is not None else None,
                    job.status,
                    job.created_at,
                    job.updated_at,
                    json.dumps(job.result, ensure_ascii=False) if job.result is not None else None,
                    job.error,
                    job.attempts,
                    job.worker_slot,
                    job.terminal_reason,
                    job.last_attempt_started_at,
                    json.dumps(job.history, ensure_ascii=False),
                    job.recovery_count,
                    job.last_recovered_at,
                    job.scheduled_at,
                ),
            )

    def _append_history(self, job: QueueJob, status: str, reason: Optional[str] = None) -> None:
        job.history.append(
            {
                "status": status,
                "reason": reason,
                "at": _now(),
                "attempts": job.attempts,
            }
        )

    def _recover_loaded_jobs(self) -> dict[str, Any]:
        summary = {
            "enabled": self.recover_on_startup,
            "recovered_running": 0,
            "queued_available": 0,
            "invalid_failed": 0,
            "at": _now(),
        }
        if not self.recover_on_startup:
            summary["queued_available"] = sum(1 for job in self.jobs.values() if job.status == "queued")
            return summary

        for job in self.jobs.values():
            if job.status == "running":
                recovered_at = _now()
                job.status = "queued"
                job.worker_slot = None
                job.scheduled_at = None
                job.terminal_reason = None
                job.recovery_count += 1
                job.last_recovered_at = recovered_at
                job.updated_at = recovered_at
                self._append_history(job, "queued", "recovered_after_restart_from_running")
                self._persist_job(job)
                summary["recovered_running"] += 1
            elif job.status not in PERSISTED_STATUSES:
                job.status = "failed"
                job.worker_slot = None
                job.scheduled_at = None
                job.terminal_reason = "invalid_persisted_status"
                job.error = f"Unsupported persisted queue status: {job.status}"
                job.updated_at = _now()
                self._append_history(job, "failed", job.terminal_reason)
                self._persist_job(job)
                summary["invalid_failed"] += 1

        summary["queued_available"] = sum(1 for job in self.jobs.values() if job.status == "queued")
        return summary

    def enqueue(self, task: str, context: Optional[dict] = None) -> QueueJob:
        job = QueueJob(job_id=str(uuid.uuid4()), task=task, context=context)
        self._append_history(job, "queued", "initial_enqueue")
        self.jobs[job.job_id] = job
        self._persist_job(job)
        return job

    def get(self, job_id: str) -> Optional[QueueJob]:
        return self.jobs.get(job_id)

    def list_jobs(self) -> list[dict]:
        return [asdict(job) for job in sorted(self.jobs.values(), key=lambda item: item.created_at, reverse=True)]

    def pending_job_ids(self) -> list[str]:
        return [
            job.job_id
            for job in sorted(self.jobs.values(), key=lambda item: item.created_at)
            if job.status == "queued"
        ]

    def active_count(self) -> int:
        return len(self._active_jobs)

    def scheduled_count(self) -> int:
        return len(self._scheduled_jobs)

    def runtime_summary(self) -> dict[str, Any]:
        counts: dict[str, int] = {}
        for job in self.jobs.values():
            counts[job.status] = counts.get(job.status, 0) + 1
        return {
            "counts": counts,
            "active_workers": self.active_count(),
            "scheduled_workers": self.scheduled_count(),
            "max_concurrency": self.max_concurrency,
            "max_attempts": self.max_attempts,
            "persistence_enabled": bool(self.db_path),
            "recover_on_startup": self.recover_on_startup,
            "startup_recovery": dict(self.startup_recovery),
        }

    def cancel(self, job_id: str) -> Optional[QueueJob]:
        job = self.jobs.get(job_id)
        if not job:
            return None
        if job.status in TERMINAL_STATUSES:
            return job
        job.status = "cancelled"
        job.terminal_reason = "cancelled_by_operator"
        job.worker_slot = None
        job.scheduled_at = None
        job.updated_at = _now()
        self._append_history(job, "cancelled", job.terminal_reason)
        self._persist_job(job)
        return job

    def requeue(self, job_id: str, *, force: bool = False) -> Optional[QueueJob]:
        job = self.jobs.get(job_id)
        if not job:
            return None
        if job.status not in {"failed", "cancelled"}:
            return job
        if job.attempts >= self.max_attempts and not force:
            job.status = "failed"
            job.terminal_reason = "max_attempts_exhausted"
            job.updated_at = _now()
            if not job.history or job.history[-1].get("reason") != job.terminal_reason:
                self._append_history(job, "failed", job.terminal_reason)
            self._persist_job(job)
            return job

        previous = job.status
        job.status = "queued"
        job.error = None
        job.result = None
        job.worker_slot = None
        job.scheduled_at = None
        job.terminal_reason = None
        job.updated_at = _now()
        self._append_history(job, "queued", f"requeued_from_{previous}")
        self._persist_job(job)
        return job

    def schedule(self, job_id: str, runner: Runner) -> bool:
        job = self.jobs.get(job_id)
        if not job or job.status != "queued":
            return False
        if job_id in self._scheduled_jobs or job_id in self._active_jobs:
            return False
        if job.attempts >= self.max_attempts:
            job.status = "failed"
            job.terminal_reason = "max_attempts_exhausted"
            job.updated_at = _now()
            self._append_history(job, "failed", job.terminal_reason)
            self._persist_job(job)
            return False

        job.scheduled_at = _now()
        job.updated_at = job.scheduled_at
        self._append_history(job, "queued", "worker_task_scheduled")
        self._persist_job(job)
        self._scheduled_jobs.add(job_id)
        try:
            asyncio.create_task(self._run_scheduled(job_id, runner))
        except RuntimeError:
            self._scheduled_jobs.discard(job_id)
            job.scheduled_at = None
            job.updated_at = _now()
            self._append_history(job, "queued", "worker_schedule_failed_no_event_loop")
            self._persist_job(job)
            return False
        return True

    def schedule_pending(self, runner: Runner) -> list[str]:
        scheduled = []
        for job_id in self.pending_job_ids():
            if self.schedule(job_id, runner):
                scheduled.append(job_id)
        return scheduled

    async def _run_scheduled(self, job_id: str, runner: Runner) -> Optional[QueueJob]:
        try:
            return await self.run_job(job_id, runner)
        finally:
            self._scheduled_jobs.discard(job_id)
            job = self.jobs.get(job_id)
            if job and job.scheduled_at is not None:
                job.scheduled_at = None
                job.updated_at = _now()
                self._persist_job(job)

    async def run_job(self, job_id: str, runner: Runner) -> Optional[QueueJob]:
        job = self.jobs.get(job_id)
        if not job or job.status != "queued":
            return job
        if job.attempts >= self.max_attempts:
            job.status = "failed"
            job.terminal_reason = "max_attempts_exhausted"
            job.updated_at = _now()
            self._append_history(job, "failed", job.terminal_reason)
            self._persist_job(job)
            return job

        async with self._semaphore:
            if job.status != "queued":
                return job
            self._active_jobs.add(job.job_id)
            job.status = "running"
            job.attempts += 1
            job.last_attempt_started_at = _now()
            job.worker_slot = f"slot-{self.active_count()}"
            job.updated_at = job.last_attempt_started_at
            self._append_history(job, "running", f"attempt_{job.attempts}_started")
            self._persist_job(job)
            try:
                result = await runner(job.task, job.context)
                if job.status == "cancelled":
                    self._append_history(job, "cancelled", "runner_result_discarded_after_cancel")
                else:
                    job.result = result
                    job.status = "completed"
                    job.error = None
                    job.terminal_reason = "runner_completed"
                    self._append_history(job, "completed", job.terminal_reason)
            except Exception as exc:
                if job.status == "cancelled":
                    self._append_history(job, "cancelled", "runner_exception_after_cancel")
                else:
                    job.error = str(exc)
                    job.status = "failed"
                    job.terminal_reason = "runner_exception"
                    self._append_history(job, "failed", job.terminal_reason)
            finally:
                job.worker_slot = None
                job.scheduled_at = None
                job.updated_at = _now()
                self._active_jobs.discard(job.job_id)
                self._persist_job(job)
            return job
