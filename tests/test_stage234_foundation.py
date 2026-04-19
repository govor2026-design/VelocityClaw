import tempfile
import textwrap
import unittest
from pathlib import Path

from velocity_claw.config.settings import Settings
from velocity_claw.core.agent import VelocityClawAgent
from velocity_claw.security.access import ExecutionProfileManager, ApprovalManager


class ExecutionProfilesTests(unittest.TestCase):
    def test_safe_profile_blocks_patch_apply(self):
        settings = Settings(execution_profile="safe")
        manager = ExecutionProfileManager(settings)
        self.assertFalse(manager.is_tool_allowed("patch.apply", "safe"))
        self.assertTrue(manager.is_tool_allowed("fs.read", "safe"))

    def test_dev_profile_allows_patch(self):
        settings = Settings(execution_profile="dev")
        manager = ExecutionProfileManager(settings)
        self.assertTrue(manager.is_tool_allowed("patch.apply", "dev"))


class ApprovalWorkflowTests(unittest.TestCase):
    def test_safe_profile_requires_approval_for_patch(self):
        settings = Settings(execution_profile="safe")
        manager = ApprovalManager(settings)
        self.assertTrue(manager.requires_approval({"tool": "patch.apply", "args": {}}))


class MemoryAndAutoFixTests(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self.db_path = str(Path(self.workspace) / "memory.db")
        self.settings = Settings(workspace_root=self.workspace, memory_db_path=self.db_path, execution_profile="dev")
        Path(self.workspace, "sample.py").write_text("value = 'old'\n")
        Path(self.workspace, "test_sample.py").write_text(textwrap.dedent(
            """
            from sample import value
            def test_value():
                assert value == 'new'
            """
        ))
        self.agent = VelocityClawAgent(self.settings)

    def test_project_facts_and_resume(self):
        self.agent.memory.save_project_fact("framework", {"name": "python"})
        self.assertEqual(self.agent.memory.load_project_fact("framework"), {"name": "python"})
        run_id = self.agent.memory.create_run("broken")
        self.agent.memory.update_run_status(run_id, "failed")
        resumed = self.agent.resume_last_failed_run()
        self.assertEqual(resumed["run_id"], run_id)

    def test_auto_fix_loop_stores_attempts(self):
        result = self.agent.run_auto_fix(
            target_test="test_sample.py",
            patch_plan=[{"op": "replace_block", "path": "sample.py", "target": "old", "replacement": "new"}],
            max_attempts=1,
        )
        self.assertEqual(result["status"], "completed")
        run = self.agent.memory.load_run(result["run_id"])
        self.assertTrue(run["fix_attempts"])
        self.assertTrue(run["artifacts"])

    def test_pending_approval_in_safe_profile(self):
        settings = Settings(workspace_root=self.workspace, memory_db_path=self.db_path, execution_profile="safe")
        agent = VelocityClawAgent(settings)
        self.assertTrue(agent.approvals.requires_approval({"tool": "patch.apply", "args": {}}))


if __name__ == "__main__":
    unittest.main()
