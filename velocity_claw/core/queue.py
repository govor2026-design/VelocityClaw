from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
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


class RunQueue:
    def __init__(self):
        self.jobs: Dict[str, QueueJob] = {}

    def enqueue(self, task: str, context: Optional[dict] = None) -> QueueJob:
        job = QueueJob(job_id=str(uuid.uuid4()), task=task, context=context)
        self.jobs[job.job_id] = job
        return job

    def get(self, job_id: str) -> Optional[QueueJob]:
        return self.jobs.get(job_id)

    async def run_job(self, job_id: str, runner):
        job = self.jobs[job_id]
        job.status = "running"
        job.updated_at = datetime.now().isoformat()
        try:
            result = await runner(job.task, job.context)
            job.result = result
            job.status = "completed"
        except Exception as e:
            job.error = str(e)
            job.status = "failed"
        job.updated_at = datetime.now().isoformat()
        return job
