import tempfile
import unittest
from pathlib import Path

from velocity_claw.config.settings import Settings
from velocity_claw.tools.test_runner import TestRunnerTool


class FailureParserAndTestRunnerV2Tests(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        Path(self.workspace, "test_sample.py").write_text("def test_ok():\n    assert True\n")
        self.runner = TestRunnerTool(Settings(workspace_root=self.workspace))

    def test_build_command_filters_extra_args_by_allowlist(self):
        cmd = self.runner._build_command(
            "pytest",
            "test_sample.py",
            ["-q", "--maxfail=1", "-kbad", "--badflag", "value"],
        )
        self.assertIn("-q", cmd)
        self.assertIn("--maxfail=1", cmd)
        self.assertNotIn("-kbad", cmd)
        self.assertNotIn("--badflag", cmd)
        self.assertNotIn("value", cmd)

    def test_parse_failed_summary_line(self):
        output = """
FAILED test_sample.py::test_value - AssertionError: expected 1 == 2
E       AssertionError: expected 1 == 2
/home/runner/work/VelocityClaw/VelocityClaw/test_sample.py:12: in test_value
        """
        failures = self.runner.parse_failures(output)
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0]["kind"], "failed")
        self.assertEqual(failures[0]["nodeid"], "test_sample.py::test_value")
        self.assertEqual(failures[0]["line"], 12)
        self.assertIn("expected 1 == 2", failures[0]["assertion"])

    def test_parse_error_summary_line(self):
        output = """
ERROR test_sample.py::test_setup - RuntimeError: setup failed
E   RuntimeError: setup failed
        """
        failures = self.runner.parse_failures(output)
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0]["kind"], "error")
        self.assertEqual(failures[0]["nodeid"], "test_sample.py::test_setup")
        self.assertIn("setup failed", failures[0]["assertion"])


if __name__ == "__main__":
    unittest.main()
