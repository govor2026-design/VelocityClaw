import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from velocity_claw.config.settings import Settings
from velocity_claw.core.agent import VelocityClawAgent


class RunRetryV2Tests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self.db_path = str(Path(self.workspace) / "memory.db")
        self.agent = VelocityClawAgent(Settings(workspace_root=self.workspace, memory_db_path=self.db_path))

    def _create_failed_run(self):
        run_id = self.agent.memory.create_run("fix broken tests")
        self.agent.memory.save_step(run_id, {
            "id": 1,
            "title": "run failing tests",
            "tool": "test.run",
            "args": {"runner": "pytest"},
            "status": "failed",
            "result": None,
            "error": "AssertionError",
            "started_at": "2026-04-25T00:00:00",
            "completed_at": "2026-04-25T00:00:01",
        })
        self.agent.memory.save_artifact(run_id, "step_1_stdout", "failure log", step_id=1, artifact_type="log")
        self.agent.memory.update_run_status(run_id, "failed")
        return run_id

    def test_build_retry_context_uses_run_report_and_forensics(self):
        run_id = self._create_failed_run()
        context = self.agent.build_retry_context(run_id)
        retry = context["retry"]
        self.assertEqual(retry["source_run_id"], run_id)
        self.assertEqual(retry["source_task"], "fix broken tests")
        self.assertEqual(retry["source_status"], "failed")
        self.assertIn("executive_summary", retry)
        self.assertEqual(retry["failed_step"]["tool"], "test.run")
        self.assertEqual(retry["recommended_strategy"]["mode"], "inspect_failed_step_first")

    async def test_retry_run_replans_with_retry_context(self):
        run_id = self._create_failed_run()
        with patch.object(self.agent, "run_task", new=AsyncMock(return_value={"status": "completed", "run_id": "retry-run"})) as run_task:
            result = await self.agent.retry_run(run_id)
        self.assertEqual(result["status"], "completed")
        called_task, called_context = run_task.call_args.args
        self.assertIn(run_id, called_task)
        self.assertEqual(called_context["retry"]["source_run_id"], run_id)


if __name__ == "__main__":
    unittest.main()
