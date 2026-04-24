import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from velocity_claw.api.server import create_app
from velocity_claw.config.settings import Settings
from velocity_claw.core.auto_fix import AutoFixLoop


class _PatchEngineStub:
    def __init__(self, diffs):
        self._diffs = diffs
        self._idx = 0

    def apply(self, patch, dry_run=False):
        diff = self._diffs[self._idx]
        self._idx += 1
        return {"diff": diff, "status": "applied"}


class _TestRunnerStub:
    def __init__(self, results):
        self._results = results
        self._idx = 0

    def run(self, runner, target=None, dry_run=False):
        result = self._results[self._idx]
        self._idx += 1
        return result


class _CodeNavStub:
    def explain_ambiguity(self, symbol):
        return {"symbol": symbol, "matches": [symbol]}


class AutoFixIntelligenceV2Tests(unittest.TestCase):
    def test_auto_fix_returns_forensics_and_stop_reason(self):
        loop = AutoFixLoop(
            _PatchEngineStub(["diff-1", "diff-2"]),
            _TestRunnerStub([
                {
                    "status": "failed",
                    "stdout": "assert one",
                    "parsed_failures": [{"nodeid": "t::a", "file": "test_a.py", "line": 10, "assertion": "x == y"}],
                },
                {
                    "status": "failed",
                    "stdout": "assert one",
                    "parsed_failures": [{"nodeid": "t::a", "file": "test_a.py", "line": 10, "assertion": "x == y"}],
                },
            ]),
            _CodeNavStub(),
        )
        result = loop.run(
            target_test="tests/test_a.py",
            patch_plan=[{"name": "foo"}, {"name": "bar"}],
            max_attempts=2,
        )
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["stop_reason"], "repeated_failure_signature")
        self.assertIn("forensics", result)
        self.assertEqual(result["forensics"]["attempt_count"], 2)
        self.assertIn("forensic_summary", result["attempts"][0])

    def test_auto_fix_api_returns_stop_reason_and_forensics(self):
        workspace = tempfile.mkdtemp()
        db_path = str(Path(workspace) / "memory.db")
        settings = Settings(workspace_root=workspace, memory_db_path=db_path)
        with patch("velocity_claw.api.server.load_settings", return_value=settings):
            app = create_app()
            client = TestClient(app)
            with patch.object(app.state.agent, "run_auto_fix", return_value={
                "mode": "auto_fix",
                "max_attempts": 2,
                "attempts": [{"attempt": 1, "status": "failed", "forensic_summary": {"failure_count": 1}}],
                "status": "failed",
                "stop_reason": "max_attempts_reached",
                "forensics": {"attempt_count": 1, "last_attempt_status": "failed"},
                "run_id": "demo-run",
            }):
                response = client.post("/auto-fix", json={
                    "target_test": "tests/test_demo.py",
                    "patch_plan": [{"name": "foo"}],
                    "runner": "pytest",
                    "max_attempts": 2,
                })
                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertEqual(payload["stop_reason"], "max_attempts_reached")
                self.assertIn("forensics", payload)


if __name__ == "__main__":
    unittest.main()
