import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from velocity_claw.api.server import create_app
from velocity_claw.config.settings import Settings
from velocity_claw.core.queue import RunQueue


class TaskQueueWorkerResilienceV2Tests(unittest.IsolatedAsyncioTestCase):
    async def test_queue_tracks_terminal_reason_and_history(self):
        queue = RunQueue(max_concurrency=1)
        job = queue.enqueue("demo task", {"k": "v"})

        async def failing_runner(task, context):
            raise RuntimeError("boom")

        await queue.run_job(job.job_id, failing_runner)
        loaded = queue.get(job.job_id)
        self.assertEqual(loaded.status, "failed")
        self.assertEqual(loaded.terminal_reason, "runner_exception")
        self.assertTrue(loaded.history)
        self.assertEqual(loaded.history[0]["status"], "queued")
        self.assertEqual(loaded.history[-1]["status"], "failed")

    async def test_queue_detail_route_exposes_history(self):
        workspace = tempfile.mkdtemp()
        db_path = str(Path(workspace) / "memory.db")
        settings = Settings(workspace_root=workspace, memory_db_path=db_path)
        with patch("velocity_claw.api.server.load_settings", return_value=settings):
            app = create_app()
            client = TestClient(app)
            job = app.state.queue.enqueue("demo task", {"k": "v"})
            stored = app.state.queue.get(job.job_id)
            stored.terminal_reason = "cancelled_by_operator"
            stored.history = [{"status": "queued", "reason": "initial_enqueue", "at": "2026-04-24T00:00:00", "attempts": 0}]
            response = client.get(f"/queue/{job.job_id}")
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["job_id"], job.job_id)
            self.assertEqual(payload["terminal_reason"], "cancelled_by_operator")
            self.assertIn("history", payload)

    async def test_dashboard_shows_queue_terminal_reason(self):
        workspace = tempfile.mkdtemp()
        db_path = str(Path(workspace) / "memory.db")
        settings = Settings(workspace_root=workspace, memory_db_path=db_path)
        with patch("velocity_claw.api.server.load_settings", return_value=settings):
            app = create_app()
            client = TestClient(app)
            job = app.state.queue.enqueue("demo task", None)
            stored = app.state.queue.get(job.job_id)
            stored.status = "failed"
            stored.terminal_reason = "runner_exception"
            dashboard = client.get("/dashboard")
            self.assertEqual(dashboard.status_code, 200)
            self.assertIn("Terminal reason", dashboard.text)
            self.assertIn("runner_exception", dashboard.text)


if __name__ == "__main__":
    unittest.main()
