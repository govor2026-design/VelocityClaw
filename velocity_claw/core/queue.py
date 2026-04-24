from __future__ import annotations

import asyncio
import json
import sqlite3
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional


@dataclass
class QueueJob:
    job_id: str
    task: str
    context: Optional[dict] = None
    status: str = "queued"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    result: Optional[dict] = None
    error: Optional[str] = None
    attempts: int = 0
    worker_slot: Optional[str] = None
    terminal_reason: Optional[str] = None
    last_attempt_started_at: Optional[str] = None
    history: list[dict] = field(default_factory=list)


class RunQueue:
    def __init__(self, db_path: Optional[str] = None, max_concurrency: int = 1):
        self.jobs: Dict[str, QueueJob] = {}
        self.db_path = db_path
        self.max_concurrency = max(1, max_concurrency)
        self._semaphore = asyncio.Semaphore(self.max_concurrency)
        self._active_jobs: set[str] = set()
        if self.db_path:
            self._ensure_tables()
            self._load_jobs_from_db()

    def _ensure_tables(self):
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
                    history TEXT
                )
                """
            )

    def _load_jobs_from_db(self):
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT job_id, task, context, status, created_at, updated_at, result, error, attempts, worker_slot, terminal_reason, last_attempt_started_at, history FROM queue_jobs"
            ).fetchall()
        for row in rows:
            self.jobs[row[0]] = QueueJob(
                job_id=row[0],
                task=row[1],
                context=json.loads(row[2]) if row[2] else None,
                status=row[3],
                created_at=row[4],
                updated_at=row[5],
                result=json.loads(row[6]) if row[6] else None,
                error=row[7],
                attempts=row[8] or 0,
                worker_slot=row[9],
                terminal_reason=row[10],
                last_attempt_started_at=row[11],
                history=json.loads(row[12]) if row[12] else [],
            )

    def _persist_job(self, job: QueueJob):
        if not self.db_path:
            return
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO queue_jobs (job_id, task, context, status, created_at, updated_at, result, error, attempts, worker_slot, terminal_reason, last_attempt_started_at, history)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    history = excluded.history
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
                ),
            )

    def _append_history(self, job: QueueJob, status: str, reason: Optional[str] = None):
        job.history.append(
            {
                "status": status,
                "reason": reason,
                "at": datetime.now().isoformat(),
                "attempts": job.attempts,
            }
        )

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

    def active_count(self) -> int:
        return len(self._active_jobs)

    def cancel(self, job_id: str) -> Optional[QueueJob]:
        job = self.jobs.get(job_id)
        if not job:
            return None
        if job.status in {"completed", "failed", "cancelled"}:
            return job
        job.status = "cancelled"
        job.terminal_reason = "cancelled_by_operator"
        job.worker_slot = None
        job.updated_at = datetime.now().isoformat()
        self._append_history(job, "cancelled", job.terminal_reason)
        self._persist_job(job)
        return job

    def requeue(self, job_id: str) -> Optional[QueueJob]:
        job = self.jobs.get(job_id)
        if not job:
            return None
        if job.status not in {"failed", "cancelled"}:
            return job
        previous = job.status
        job.status = "queued"
        job.error = None
        job.result = None
        job.worker_slot = None
        job.terminal_reason = None
        job.updated_at = datetime.now().isoformat()
        self._append_history(job, "queued", f"requeued_from_{previous}")
        self._persist_job(job)
        return job

    async def run_job(self, job_id: str, runner):
        job = self.jobs[job_id]
        if job.status == "cancelled":
            return job
        async with self._semaphore:
            if job.status == "cancelled":
                return job
            self._active_jobs.add(job.job_id)
            job.status = "running"
            job.attempts += 1
            job.last_attempt_started_at = datetime.now().isoformat()
            job.worker_slot = f"slot-{self.active_count()}"
            job.updated_at = datetime.now().isoformat()
            self._append_history(job, "running", f"attempt_{job.attempts}_started")
            self._persist_job(job)
            try:
                result = await runner(job.task, job.context)
                job.result = result
                job.status = "completed"
                job.error = None
                job.terminal_reason = "runner_completed"
                self._append_history(job, "completed", job.terminal_reason)
            except Exception as e:
                job.error = str(e)
                job.status = "failed"
                job.terminal_reason = "runner_exception"
                self._append_history(job, "failed", job.terminal_reason)
            finally:
                job.worker_slot = None
                job.updated_at = datetime.now().isoformat()
                self._persist_job(job)
                self._active_jobs.discard(job.job_id)
            return job
