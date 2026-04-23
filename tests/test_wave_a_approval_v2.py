import tempfile
import unittest
from pathlib import Path

from velocity_claw.config.settings import Settings
from velocity_claw.core.agent import VelocityClawAgent


class ApprovalWorkflowV2Tests(unittest.IsolatedAsyncioTestCase):
    async def test_run_enters_awaiting_approval_and_history_is_recorded(self):
        workspace = tempfile.mkdtemp()
        db_path = str(Path(workspace) / "memory.db")
        settings = Settings(workspace_root=workspace, memory_db_path=db_path, execution_profile="safe")
        Path(workspace, "sample.py").write_text("value = 'old'\n")
        agent = VelocityClawAgent(settings)

        async def fake_plan(task, context=None):
            return {
                "task": task,
                "steps": [
                    {"id": 1, "title": "patch sample", "tool": "patch.apply", "args": {"patch": {"op": "replace_block", "path": "sample.py", "target": "old", "replacement": "new"}}, "expected_output": "patched"}
                ],
            }

        agent.planner.create_plan = fake_plan
        result = await agent.run_task("patch")
        self.assertEqual(result["status"], "awaiting_approval")
        history = agent.get_approval_history(result["run_id"])
        self.assertTrue(history)
        self.assertEqual(history[0]["decision"], "requested")

    async def test_approve_step_resumes_saved_plan(self):
        workspace = tempfile.mkdtemp()
        db_path = str(Path(workspace) / "memory.db")
        settings = Settings(workspace_root=workspace, memory_db_path=db_path, execution_profile="safe")
        Path(workspace, "sample.py").write_text("value = 'old'\n")
        agent = VelocityClawAgent(settings)

        async def fake_plan(task, context=None):
            return {
                "task": task,
                "steps": [
                    {"id": 1, "title": "patch sample", "tool": "patch.apply", "args": {"patch": {"op": "replace_block", "path": "sample.py", "target": "old", "replacement": "new"}}, "expected_output": "patched"},
                    {"id": 2, "title": "read patched file", "tool": "fs.read", "args": {"path": "sample.py"}, "expected_output": "content"}
                ],
            }

        agent.planner.create_plan = fake_plan
        result = await agent.run_task("patch")
        approve = await agent.approve_step(result["run_id"], 1, actor="tester", reason="approved")
        self.assertIn("resume", approve)
        self.assertEqual(approve["resume"]["status"], "completed")
        self.assertIn("new", Path(workspace, "sample.py").read_text())

    async def test_reject_step_records_history(self):
        workspace = tempfile.mkdtemp()
        db_path = str(Path(workspace) / "memory.db")
        settings = Settings(workspace_root=workspace, memory_db_path=db_path, execution_profile="safe")
        Path(workspace, "sample.py").write_text("value = 'old'\n")
        agent = VelocityClawAgent(settings)

        async def fake_plan(task, context=None):
            return {
                "task": task,
                "steps": [
                    {"id": 1, "title": "patch sample", "tool": "patch.apply", "args": {"patch": {"op": "replace_block", "path": "sample.py", "target": "old", "replacement": "new"}}, "expected_output": "patched"}
                ],
            }

        agent.planner.create_plan = fake_plan
        result = await agent.run_task("patch")
        reject = agent.reject_step(result["run_id"], 1, actor="tester", reason="later")
        self.assertEqual(reject["decision"], "rejected")
        history = agent.get_approval_history(result["run_id"])
        self.assertEqual(history[-1]["decision"], "rejected")


if __name__ == "__main__":
    unittest.main()
