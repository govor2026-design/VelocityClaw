import tempfile
import unittest
from unittest.mock import AsyncMock
from velocity_claw.config.settings import Settings
from velocity_claw.core.agent import VelocityClawAgent


class AgentTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.settings = Settings(workspace_root=tempfile.mkdtemp(), memory_db_path=tempfile.mktemp(suffix=".db"))
        self.agent = VelocityClawAgent(self.settings)

    async def test_agent_saves_complete_step_metadata(self):
        self.agent.planner.create_plan = AsyncMock(return_value={
            "task": "test",
            "steps": [{
                "id": 1,
                "title": "read file",
                "tool": "fs.read",
                "args": {"path": "hello.txt"},
                "expected_output": "content",
            }],
        })
        self.agent.executor.execute_step = AsyncMock(return_value={
            "id": 1,
            "title": "read file",
            "tool": "fs.read",
            "args": {"path": "hello.txt"},
            "status": "success",
            "result": "hello",
            "error": None,
        })
        report = await self.agent.run_task("test")
        loaded = self.agent.memory.load_run(report["run_id"])
        self.assertEqual(loaded["steps"][0]["tool"], "fs.read")
        self.assertEqual(loaded["steps"][0]["args"], {"path": "hello.txt"})
        self.assertIsNotNone(loaded["steps"][0]["started_at"])
        self.assertIsNotNone(loaded["steps"][0]["completed_at"])


if __name__ == "__main__":
    unittest.main()
