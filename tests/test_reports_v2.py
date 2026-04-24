import tempfile
import unittest
from pathlib import Path

from velocity_claw.config.settings import Settings
from velocity_claw.memory.store import MemoryStore


class ReportsV2Tests(unittest.TestCase):
    def test_run_report_exists(self):
        workspace = tempfile.mkdtemp()
        db_path = str(Path(workspace) / "memory.db")
        store = MemoryStore(Settings(workspace_root=workspace, memory_db_path=db_path))
        run_id = store.create_run("demo run")
        store.save_step(run_id, {
            "id": 1,
            "title": "run tests",
            "tool": "test.run",
            "args": {"runner": "pytest"},
            "status": "failed",
            "result": None,
            "error": "AssertionError",
            "started_at": "2026-04-24T00:00:00",
            "completed_at": "2026-04-24T00:00:01",
        })
        store.save_artifact(run_id, "step_1_stdout", "trace log", step_id=1, artifact_type="log")
        run = store.load_run(run_id)
        report = run["report"]
        self.assertIn("executive_summary", report)
        self.assertEqual(report["artifact_overview"]["total"], 1)
        self.assertEqual(report["step_overview"]["failed"], 1)
        self.assertTrue(report["key_steps"])


if __name__ == "__main__":
    unittest.main()
