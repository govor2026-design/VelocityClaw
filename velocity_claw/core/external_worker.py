from __future__ import annotations

import asyncio
import os
import socket
import uuid
from collections.abc import Callable
from contextlib import suppress
from inspect import isawaitable
from typing import Any

from velocity_claw.config.settings import Settings
from velocity_claw.core.agent import VelocityClawAgent
from velocity_claw.core.queue import QueueJob, RunQueue
from velocity_claw.logs.logger import get_logger


class ExternalQueueWorker:
    """Poll and execute persistent queue jobs from a separate process."""

    def __init__(
        self,
        settings: Settings,
        *,
        agent: Any | None = None,
        queue: RunQueue | None = None,
        worker_id: str | None = None,
    ) -> None:
        self.settings = settings
        self.agent = agent or VelocityClawAgent(settings)
        self.queue = queue or RunQueue(
            db_path=f"{settings.memory_db_path}.queue",
            max_concurrency=settings.queue_max_concurrency,
            max_attempts=settings.queue_max_attempts,
            recover_on_startup=False,
        )
        self.queue.configure_execution_mode("external")
        self.worker_id = worker_id or self._default_worker_id()
        self.logger = get_logger("velocity_claw.external_worker")
        self._active: dict[str, asyncio.Task] = {}

    @staticmethod
    def _default_worker_id() -> str:
        host = socket.gethostname() or "host"
        return f"{host}:{os.getpid()}:{uuid.uuid4().hex[:8]}"

    async def _heartbeat(self, job_id: str, finished: asyncio.Event) -> None:
        interval = max(0.5, min(30.0, self.settings.queue_worker_lease_seconds / 3))
        while not finished.is_set():
            try:
                await asyncio.wait_for(finished.wait(), timeout=interval)
            except asyncio.TimeoutError:
                if not self.queue.heartbeat_claim(
                    job_id,
                    self.worker_id,
                    self.settings.queue_worker_lease_seconds,
                ):
                    self.logger.warning("Lost external worker lease for job %s", job_id)
                    return

    async def _execute_claim(self, job: QueueJob) -> None:
        finished = asyncio.Event()
        heartbeat = asyncio.create_task(
            self._heartbeat(job.job_id, finished),
            name=f"velocity-claw-heartbeat-{job.job_id}",
        )
        try:
            result = await self.agent.run_task(job.task, job.context)
            current = self.queue.finish_claim(
                job.job_id,
                self.worker_id,
                result=result,
            )
            if current is not None and current.status != "completed":
                self.logger.info(
                    "Discarded result for job %s because persisted status is %s",
                    job.job_id,
                    current.status,
                )
        except asyncio.CancelledError:
            self.queue.release_claim(job.job_id, self.worker_id)
            raise
        except Exception as exc:
            self.logger.exception("External worker job %s failed", job.job_id)
            self.queue.finish_claim(
                job.job_id,
                self.worker_id,
                error=str(exc),
            )
        finally:
            finished.set()
            heartbeat.cancel()
            with suppress(asyncio.CancelledError):
                await heartbeat

    def _claim_available(self) -> list[str]:
        claimed: list[str] = []
        while len(self._active) < self.settings.queue_max_concurrency:
            job = self.queue.claim_next(
                self.worker_id,
                self.settings.queue_worker_lease_seconds,
            )
            if job is None:
                break
            task = asyncio.create_task(
                self._execute_claim(job),
                name=f"velocity-claw-external-job-{job.job_id}",
            )
            self._active[job.job_id] = task
            claimed.append(job.job_id)
        return claimed

    def _reap_completed(self) -> None:
        for job_id, task in list(self._active.items()):
            if not task.done():
                continue
            self._active.pop(job_id, None)
            with suppress(asyncio.CancelledError):
                task.result()

    async def run_once(self) -> bool:
        job = self.queue.claim_next(
            self.worker_id,
            self.settings.queue_worker_lease_seconds,
        )
        if job is None:
            return False
        await self._execute_claim(job)
        return True

    async def run_forever(
        self,
        stop_requested: Callable[[], bool] | None = None,
    ) -> dict[str, Any]:
        stop_requested = stop_requested or (lambda: False)
        poll_seconds = self.settings.queue_worker_poll_ms / 1000.0
        self.logger.info(
            "External queue worker %s started with concurrency %s",
            self.worker_id,
            self.settings.queue_max_concurrency,
        )
        try:
            while not stop_requested():
                self._reap_completed()
                self._claim_available()
                await asyncio.sleep(poll_seconds)
        finally:
            for task in self._active.values():
                task.cancel()
            if self._active:
                await asyncio.gather(*self._active.values(), return_exceptions=True)
            self._active.clear()
            close = getattr(self.agent, "close", None)
            if close is not None:
                close_result = close()
                if isawaitable(close_result):
                    await close_result
        return {
            "status": "stopped",
            "worker_id": self.worker_id,
            "active_jobs": 0,
        }
