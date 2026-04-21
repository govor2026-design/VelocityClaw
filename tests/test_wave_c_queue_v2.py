import tempfile
import unittest
from pathlib import Path

from velocity_claw.core.queue import RunQueue


class QueuePersistenceV2Tests(unittest.IsolatedAsyncioTestCase):
    async def test_queue_persists_jobs(self):
        workspace = tempfile.mkdtemp()
        db_path = str(Path(workspace) / "queue.db")
        queue = RunQueue(db_path=db_path)
        job = queue.enqueue("task-one", {"x": 1})

        queue_reloaded = RunQueue(db_path=db_path)
        loaded = queue_reloaded.get(job.job_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.task, "task-one")
        self.assertEqual(loaded.context, {"x": 1})

    async def test_queue_cancel_and_list(self):
        workspace = tempfile.mkdtemp()
        db_path = str(Path(workspace) / "queue.db")
        queue = RunQueue(db_path=db_path)
        job = queue.enqueue("task-two")
        queue.cancel(job.job_id)
        listed = queue.list_jobs()
        self.assertTrue(listed)
        self.assertEqual(listed[0]["status"], "cancelled")


if __name__ == "__main__":
    unittest.main()
