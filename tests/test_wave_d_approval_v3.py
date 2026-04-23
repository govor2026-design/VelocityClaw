import tempfile
import unittest
from pathlib import Path

from velocity_claw.config.settings import Settings
from velocity_claw.core.agent import VelocityClawAgent


class ApprovalContinuationV3Tests(unittest.IsolatedAsyncioTestCase):
    async def test_resume_can_pause_again_on_next_sensitive_step(self):
        workspace = tempfile.mkdtemp()
        db_path = str(Path(workspace) / "memory.db")
        settings = Settings(workspace_root=workspace, memory_db_path=db_path, execution_profile="safe")
        Path(workspace, "sample.py").write_text("print('old')\n")
        agent = VelocityClawAgent(settings)

        async def fake_plan(task, context=None):
            return {
                "task": task,
                "steps": [
                    {"id": 1, "title": "first patch", "tool": "patch.apply", "args": {"patch": {"op": "replace_block", "path": "sample.py", "target": "old", "replacement": "mid"}}, "expected_output": "patched"},
                    {"id": 2, "title": "second patch", "tool": "patch.apply", "args": {"patch": {"op": "replace_block", "path": "sample.py", "target": "mid", "replacement": "new"}}, "expected_output": "patched"},
                ],
            }

        agent.planner.create_plan = fake_plan
        initial = await agent.run_task("patch")
        self.assertEqual(initial["status"], "awaiting_approval")
        approve = await agent.approve_step(initial["run_id"], 1, actor="tester", reason="continue")
        self.assertEqual(approve["resume"]["status"], "awaiting_approval")
        self.assertEqual(approve["resume"]["boundary_step_id"], 2)

    async def test_reject_sets_rejected_status(self):
        workspace = tempfile.mkdtemp()
        db_path = str(Path(workspace) / "memory.db")
        settings = Settings(workspace_root=workspace, memory_db_path=db_path, execution_profile="safe")
        Path(workspace, "sample.py").write_text("print('old')\n")
        agent = VelocityClawAgent(settings)

        async def fake_plan(task, context=None):
            return {
                "task": task,
                "steps": [
                    {"id": 1, "title": "first patch", "tool": "patch.apply", "args": {"patch": {"op": "replace_block", "path": "sample.py", "target": "old", "replacement": "new"}}, "expected_output": "patched"}
                ],
            }

        agent.planner.create_plan = fake_plan
        initial = await agent.run_task("patch")
        agent.reject_step(initial["run_id"], 1, actor="tester", reason="stop")
        run = agent.memory.load_run(initial["run_id"])
        self.assertEqual(run["status"], "rejected")


if __name__ == "__main__":
    unittest.main()
