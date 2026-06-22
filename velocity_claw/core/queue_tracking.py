from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any


def install_direct_run_tracking(queue: Any) -> None:
    """Make legacy direct ``run_job`` calls participate in orchestration v2.

    The classic API route creates an asyncio task around ``run_job``. This adapter
    registers that task in the same task registry used by ``schedule`` and refuses
    to start it when tracked capacity is already full. The job then stays queued
    and is picked up by the normal FIFO refill path.
    """
    if getattr(queue, "_direct_run_tracking_installed", False):
        return

    original_run_job = queue.run_job

    async def tracked_run_job(job_id, runner):
        job = queue.get(job_id)
        current_task = asyncio.current_task()

        if current_task is None or job_id in queue._job_tasks:
            return await original_run_job(job_id, runner)

        queue._last_runner = runner
        if not queue._accepting_work or queue.tracked_task_count() >= queue.max_concurrency:
            return job
        if job is None or job.status != "queued":
            return job

        scheduled_at = datetime.now().isoformat()
        job.scheduled_at = scheduled_at
        job.updated_at = scheduled_at
        queue._append_history(job, "queued", "legacy_worker_task_tracked")
        queue._persist_job(job)
        queue._scheduled_jobs.add(job_id)
        queue._job_tasks[job_id] = current_task
        current_task.add_done_callback(
            lambda completed, current_job=job_id: queue._on_task_done(current_job, runner, completed)
        )
        return await original_run_job(job_id, runner)

    queue.run_job = tracked_run_job
    queue._direct_run_tracking_installed = True
