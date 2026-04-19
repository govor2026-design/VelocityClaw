import tempfile
import textwrap
import unittest
from pathlib import Path

from velocity_claw.config.settings import Settings
from velocity_claw.tools.test_runner import TestRunnerTool


class TestRunnerV2Tests(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self.settings = Settings(workspace_root=self.workspace)
        self.runner = TestRunnerTool(self.settings)
        Path(self.workspace, "test_sample.py").write_text(textwrap.dedent(
            """
            import pytest

            @pytest.mark.fast
            def test_ok():
                assert 1 == 1

            def test_bad():
                assert 1 == 2
            """
        ))

    def test_extract_summary_has_collected(self):
        result = self.runner.run("pytest", target="test_sample.py", timeout=30)
        self.assertIn("collected", result["summary"])
        self.assertGreaterEqual(result["summary"]["collected"], 1)

    def test_dry_run_keeps_new_fields(self):
        result = self.runner.run("pytest", target="test_sample.py", dry_run=True, keyword="ok", marker="fast")
        self.assertEqual(result["status"], "simulated")
        self.assertEqual(result["keyword"], "ok")
        self.assertEqual(result["marker"], "fast")

    def test_keyword_and_marker_are_reflected_in_command(self):
        result = self.runner.run("pytest", target="test_sample.py", dry_run=True, keyword="ok", marker="fast")
        self.assertIn("-k", result["command"])
        self.assertIn("ok", result["command"])
        self.assertIn("-m", result["command"])
        self.assertIn("fast", result["command"])

    def test_parse_failures_has_nodeid(self):
        result = self.runner.run("pytest", target="test_sample.py", timeout=30)
        self.assertTrue(result["parsed_failures"])
        self.assertIn("nodeid", result["parsed_failures"][0])


if __name__ == "__main__":
    unittest.main()
