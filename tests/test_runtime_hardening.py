import tempfile
import unittest
from pathlib import Path

from velocity_claw.config.settings import Settings
from velocity_claw.core.agent import VelocityClawAgent


class RuntimeHardeningTests(unittest.IsolatedAsyncioTestCase):
    async def test_async_approve_step_resumes_without_asyncio_run(self):
        workspace = tempfile.mkdtemp()
        db_path = str(Path(workspace) / "memory.db")
        settings = Settings(workspace_root=workspace, memory_db_path=db_path, execution_profile="safe")
        Path(workspace, "sample.py").write_text("print('old')\n")
        agent = VelocityClawAgent(settings)

        async def fake_plan(task, context=None):
            return {
                "task": task,
                "steps": [
                    {
                        "id": 1,
                        "title": "patch file",
                        "tool": "patch.apply",
                        "args": {"patch": {"op": "replace_block", "path": "sample.py", "target": "old", "replacement": "new"}},
                        "expected_output": "patched",
                    }
                ],
            }

        agent.planner.create_plan = fake_plan
        initial = await agent.run_task("patch")
        self.assertEqual(initial["status"], "awaiting_approval")

        approved = await agent.approve_step(initial["run_id"], 1, actor="tester", reason="continue")
        self.assertIn("resume", approved)
        self.assertEqual(approved["resume"]["status"], "completed")


if __name__ == "__main__":
    unittest.main()
