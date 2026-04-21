import tempfile
import textwrap
import unittest
from pathlib import Path

from velocity_claw.config.settings import Settings
from velocity_claw.core.auto_fix import AutoFixLoop
from velocity_claw.tools.code_nav import CodeNavigationTool
from velocity_claw.tools.patch import PatchEngine
from velocity_claw.tools.test_runner import TestRunnerTool


class AutoFixLoopV2Tests(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self.settings = Settings(workspace_root=self.workspace)
        Path(self.workspace, "sample.py").write_text("value = 'old'\n")
        Path(self.workspace, "test_sample.py").write_text(textwrap.dedent(
            """
            from sample import value

            def test_value():
                assert value == 'new'
            """
        ))
        self.loop = AutoFixLoop(PatchEngine(self.settings), TestRunnerTool(self.settings), CodeNavigationTool(self.settings))

    def test_completed_run_has_repair_summary(self):
        result = self.loop.run(
            target_test="test_sample.py",
            patch_plan=[{"op": "replace_block", "path": "sample.py", "target": "old", "replacement": "new"}],
            max_attempts=1,
        )
        self.assertEqual(result["status"], "completed")
        self.assertIn("repair_summary", result["attempts"][0])

    def test_repeated_patch_signature_stops(self):
        result = self.loop.run(
            target_test="test_sample.py",
            patch_plan=[
                {"op": "replace_block", "path": "sample.py", "target": "old", "replacement": "new"},
                {"op": "replace_block", "path": "sample.py", "target": "old", "replacement": "new"},
            ],
            max_attempts=2,
            dry_run=True,
        )
        self.assertEqual(result["attempts"][-1]["stop_reason"], "repeated_patch_signature")

    def test_failure_signature_present_on_failed_attempt(self):
        result = self.loop.run(
            target_test="test_sample.py",
            patch_plan=[{"op": "append", "path": "sample.py", "content": "\nother = 1\n"}],
            max_attempts=1,
        )
        self.assertEqual(result["status"], "failed")
        self.assertTrue(result["attempts"][0]["failure_signature"])


if __name__ == "__main__":
    unittest.main()
