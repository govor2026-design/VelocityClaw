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
    except (TypeError, ValueError):
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
        recover_on_startup: bool = False,
    ):
        self.jobs: Dict[str, QueueJob] = {}
        self.db_path = db_path
        self.max_concurrency = max(1, int(max_concurrency))
        self.max_attempts = max(1, int(max_attempts))
        self.recover_on_startup = bool(recover_on_startup)
        self._semaphore = asyncio.Semaphore(self.max_concurrency)
        self._active_jobs: set[str] = set()
        self._scheduled_jobs: set[str] = set()
        self._job_tasks: dict[str, asyncio.Task] = {}
        self._active_slots: dict[str, str] = {}
        self._accepting_work = True
        self._last_runner: Optional[Runner] = None
        self._startup_recovery_applied = False
        self.startup_recovery: dict[str, Any] = self._empty_recovery_summary()
        if self.db_path:
            self._ensure_tables()
            self._load_jobs_from_db()
            self.startup_recovery["queued_available"] = sum(
                1 for job in self.jobs.values() if job.status == "queued"
            )
            if self.recover_on_startup:
                self.startup_recovery = self._recover_loaded_jobs()
                self._startup_recovery_applied = True

    def _empty_recovery_summary(self) -> dict[str, Any]:
        return {
            "enabled": self.recover_on_startup,
            "recovered_running": 0,
            "queued_available": 0,
            "invalid_failed": 0,
            "at": None,
        }

    def configure_runtime(
        self,
        *,
        max_concurrency: int | None = None,
        max_attempts: int | None = None,
        recover_on_startup: bool | None = None,
    ) -> dict[str, Any]:
        if max_concurrency is not None:
            configured = max(1, int(max_concurrency))
            if configured != self.max_concurrency:
                if self._job_tasks or self._active_jobs:
                    raise RuntimeError("Queue concurrency cannot change while workers are active")
                self.max_concurrency = configured
                self._semaphore = asyncio.Semaphore(self.max_concurrency)
        if max_attempts is not None:
            self.max_attempts = max(1, int(max_attempts))
        if recover_on_startup is not None:
            self.recover_on_startup = bool(recover_on_startup)

        if self.recover_on_startup and not self._startup_recovery_applied:
            self.startup_recovery = self._recover_loaded_jobs()
            self._startup_recovery_applied = True
        else:
            self.startup_recovery["enabled"] = self.recover_on_startup
            self.startup_recovery["queued_available"] = sum(
                1 for job in self.jobs.values() if job.status == "queued"
            )
        return self.runtime_summary()

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
                invalid_status = job.status
                job.status = "failed"
                job.worker_slot = None
                job.scheduled_at = None
                job.terminal_reason = "invalid_persisted_status"
                job.error = f"Unsupported persisted queue status: {invalid_status}"
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

    def tracked_task_count(self) -> int:
        return sum(1 for task in self._job_tasks.values() if not task.done())

    def runtime_summary(self) -> dict[str, Any]:
        counts: dict[str, int] = {}
        for job in self.jobs.values():
            counts[job.status] = counts.get(job.status, 0) + 1
        return {
            "orchestrator": "v2",
            "counts": counts,
            "accepting_work": self._accepting_work,
            "active_workers": self.active_count(),
            "scheduled_workers": self.scheduled_count(),
            "tracked_tasks": self.tracked_task_count(),
            "active_slots": dict(sorted(self._active_slots.items(), key=lambda item: item[1])),
            "available_slots": max(0, self.max_concurrency - self.active_count()),
            "scheduling_capacity": max(0, self.max_concurrency - self.tracked_task_count()),
            "max_concurrency": self.max_concurrency,
            "max_attempts": self.max_attempts,
            "persistence_enabled": bool(self.db_path),
            "recover_on_startup": self.recover_on_startup,
            "startup_recovery": dict(self.startup_recovery),
        }

    def pause(self) -> dict[str, Any]:
        self._accepting_work = False
        return self.runtime_summary()

    def resume(self, runner: Optional[Runner] = None) -> list[str]:
        self._accepting_work = True
        if runner is not None:
            self._last_runner = runner
        if self._last_runner is None:
            return []
        return self.schedule_pending(self._last_runner)

    def _cancel_task(self, task: asyncio.Task) -> None:
        if task.done():
            return
        try:
            task_loop = task.get_loop()
            try:
                current_loop = asyncio.get_running_loop()
            except RuntimeError:
                current_loop = None
            if current_loop is task_loop:
                task.cancel()
            else:
                task_loop.call_soon_threadsafe(task.cancel)
        except RuntimeError:
            pass

    def cancel(self, job_id: str) -> Optional[QueueJob]:
        job = self.jobs.get(job_id)
        if not job:
            return None
        if job.status in TERMINAL_STATUSES:
            return job
        was_running = job.status == "running"
        job.status = "cancelled"
        job.terminal_reason = "cancelled_by_operator"
        if not was_running:
            job.worker_slot = None
        job.scheduled_at = None
        job.updated_at = _now()
        self._append_history(job, "cancelled", job.terminal_reason)
        self._persist_job(job)
        task = self._job_tasks.get(job_id)
        if task is not None:
            self._cancel_task(task)
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

    def _allocate_worker_slot(self, job_id: str) -> str:
        used = set(self._active_slots.values())
        for index in range(1, self.max_concurrency + 1):
            slot = f"slot-{index}"
            if slot not in used:
                self._active_slots[job_id] = slot
                return slot
        slot = f"slot-{len(used) + 1}"
        self._active_slots[job_id] = slot
        return slot

    def _on_task_done(self, job_id: str, runner: Runner, task: asyncio.Task) -> None:
        self._job_tasks.pop(job_id, None)
        self._scheduled_jobs.discard(job_id)
        job = self.jobs.get(job_id)
        if job is not None:
            if task.cancelled() and job.status == "queued":
                job.status = "cancelled"
                job.terminal_reason = "worker_task_cancelled_before_start"
                self._append_history(job, "cancelled", job.terminal_reason)
            if job.scheduled_at is not None:
                job.scheduled_at = None
                job.updated_at = _now()
            self._persist_job(job)
        if self._accepting_work:
            self.schedule_pending(runner)

    def schedule(self, job_id: str, runner: Runner) -> bool:
        job = self.jobs.get(job_id)
        if not self._accepting_work or not job or job.status != "queued":
            return False
        if job_id in self._job_tasks or job_id in self._scheduled_jobs or job_id in self._active_jobs:
            return False
        if self.tracked_task_count() >= self.max_concurrency:
            return False
        if job.attempts >= self.max_attempts:
            job.status = "failed"
            job.terminal_reason = "max_attempts_exhausted"
            job.updated_at = _now()
            self._append_history(job, "failed", job.terminal_reason)
            self._persist_job(job)
            return False

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            job.scheduled_at = None
            job.updated_at = _now()
            self._append_history(job, "queued", "worker_schedule_failed_no_event_loop")
            self._persist_job(job)
            return False

        self._last_runner = runner
        job.scheduled_at = _now()
        job.updated_at = job.scheduled_at
        self._append_history(job, "queued", "worker_task_scheduled")
        self._persist_job(job)
        self._scheduled_jobs.add(job_id)
        task = loop.create_task(self._run_scheduled(job_id, runner), name=f"velocity-claw-job-{job_id}")
        self._job_tasks[job_id] = task
        task.add_done_callback(lambda completed, current_job=job_id: self._on_task_done(current_job, runner, completed))
        return True

    def schedule_pending(self, runner: Runner) -> list[str]:
        self._last_runner = runner
        if not self._accepting_work:
            return []
        scheduled: list[str] = []
        for job_id in self.pending_job_ids():
            if self.tracked_task_count() >= self.max_concurrency:
                break
            if self.schedule(job_id, runner):
                scheduled.append(job_id)
        return scheduled

    async def _run_scheduled(self, job_id: str, runner: Runner) -> Optional[QueueJob]:
        return await self.run_job(job_id, runner)

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

        try:
            async with self._semaphore:
                if job.status != "queued":
                    return job
                self._active_jobs.add(job.job_id)
                job.status = "running"
                job.attempts += 1
                job.last_attempt_started_at = _now()
                job.worker_slot = self._allocate_worker_slot(job.job_id)
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
                except asyncio.CancelledError:
                    if job.status != "cancelled":
                        job.status = "cancelled"
                        job.terminal_reason = "worker_task_cancelled"
                    self._append_history(job, "cancelled", "runner_task_cancelled")
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
                    self._active_slots.pop(job.job_id, None)
                    self._active_jobs.discard(job.job_id)
                    self._persist_job(job)
                return job
        except asyncio.CancelledError:
            if job.status != "cancelled":
                job.status = "cancelled"
                job.terminal_reason = "worker_task_cancelled_before_start"
            job.worker_slot = None
            job.scheduled_at = None
            job.updated_at = _now()
            self._active_slots.pop(job.job_id, None)
            self._active_jobs.discard(job.job_id)
            self._append_history(job, "cancelled", job.terminal_reason)
            self._persist_job(job)
            return job

    async def drain(self, timeout_seconds: float = 10.0) -> dict[str, Any]:
        self._accepting_work = False
        tasks = [task for task in self._job_tasks.values() if not task.done()]
        if not tasks:
            return {"status": "drained", "timed_out": False, "pending_tasks": 0, "queue": self.runtime_summary()}
        _, pending = await asyncio.wait(tasks, timeout=max(0.0, float(timeout_seconds)))
        return {
            "status": "timeout" if pending else "drained",
            "timed_out": bool(pending),
            "pending_tasks": len(pending),
            "queue": self.runtime_summary(),
        }

    async def shutdown(self, timeout_seconds: float = 10.0, *, cancel_running: bool = True) -> dict[str, Any]:
        self._accepting_work = False
        tasks = [task for task in self._job_tasks.values() if not task.done()]
        if cancel_running:
            for job_id in list(self._job_tasks):
                self.cancel(job_id)
        if tasks:
            _, pending = await asyncio.wait(tasks, timeout=max(0.0, float(timeout_seconds)))
        else:
            pending = set()
        return {
            "status": "timeout" if pending else "stopped",
            "timed_out": bool(pending),
            "pending_tasks": len(pending),
            "cancel_running": cancel_running,
            "queue": self.runtime_summary(),
        }
