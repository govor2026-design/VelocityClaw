import tempfile
import unittest
from pathlib import Path

from velocity_claw.config.settings import Settings
from velocity_claw.core.agent import VelocityClawAgent


class ArtifactRunDetailV2Tests(unittest.IsolatedAsyncioTestCase):
    async def test_run_has_groupable_artifacts(self):
        workspace = tempfile.mkdtemp()
        db_path = str(Path(workspace) / "memory.db")
        settings = Settings(workspace_root=workspace, memory_db_path=db_path, execution_profile="dev")
        Path(workspace, "sample.py").write_text("print('old')\n")
        agent = VelocityClawAgent(settings)

        async def fake_plan(task, context=None):
            return {
                "task": task,
                "steps": [
                    {"id": 1, "title": "patch file", "tool": "patch.apply", "args": {"patch": {"op": "replace_block", "path": "sample.py", "target": "old", "replacement": "new"}}, "expected_output": "patched"}
                ],
            }

        agent.planner.create_plan = fake_plan
        result = await agent.run_task("patch")
        run = agent.memory.load_run(result["run_id"])
        self.assertTrue(run["artifacts"])
        self.assertEqual(run["status"], "completed")


if __name__ == "__main__":
    unittest.main()
