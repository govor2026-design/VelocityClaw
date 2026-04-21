import tempfile
import unittest
from pathlib import Path

from velocity_claw.core.queue import RunQueue


class WorkerOrchestrationV2Tests(unittest.IsolatedAsyncioTestCase):
    async def test_queue_has_max_concurrency_and_active_count(self):
        workspace = tempfile.mkdtemp()
        db_path = str(Path(workspace) / "queue.db")
        queue = RunQueue(db_path=db_path, max_concurrency=2)
        self.assertEqual(queue.max_concurrency, 2)
        self.assertEqual(queue.active_count(), 0)

    async def test_requeue_failed_or_cancelled_job(self):
        workspace = tempfile.mkdtemp()
        db_path = str(Path(workspace) / "queue.db")
        queue = RunQueue(db_path=db_path, max_concurrency=1)
        job = queue.enqueue("task")
        queue.cancel(job.job_id)
        requeued = queue.requeue(job.job_id)
        self.assertEqual(requeued.status, "queued")
        self.assertEqual(requeued.attempts, 0)


if __name__ == "__main__":
    unittest.main()
