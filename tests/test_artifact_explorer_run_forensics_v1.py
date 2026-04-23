import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from velocity_claw.api.server import create_app
from velocity_claw.config.settings import Settings
from velocity_claw.memory.store import MemoryStore


class ArtifactExplorerRunForensicsV1Tests(unittest.TestCase):
    def test_memory_store_builds_run_forensics(self):
        workspace = tempfile.mkdtemp()
        db_path = str(Path(workspace) / "memory.db")
        store = MemoryStore(Settings(workspace_root=workspace, memory_db_path=db_path))
        run_id = store.create_run("debug failing run")
        store.save_step(run_id, {
            "id": 1,
            "title": "run tests",
            "tool": "test.run",
            "args": {"runner": "pytest"},
            "status": "failed",
            "result": None,
            "error": "AssertionError",
            "started_at": "2026-04-23T00:00:00",
            "completed_at": "2026-04-23T00:00:01",
        })
        store.save_artifact(run_id, "step_1_stdout", "trace log", step_id=1, artifact_type="log")
        store.save_artifact(run_id, "step_1_diff", "diff preview", step_id=1, artifact_type="diff")
        run = store.load_run(run_id)
        forensic = run["forensics"]
        self.assertEqual(forensic["step_count"], 1)
        self.assertEqual(forensic["artifact_count"], 2)
        self.assertEqual(forensic["failed_step"]["tool"], "test.run")
        self.assertIn("log", forensic["artifact_counts_by_type"])

    def test_run_forensics_route_and_dashboard(self):
        workspace = tempfile.mkdtemp()
        db_path = str(Path(workspace) / "memory.db")
        settings = Settings(workspace_root=workspace, memory_db_path=db_path)
        with patch("velocity_claw.api.server.load_settings", return_value=settings):
            app = create_app()
            client = TestClient(app)
            run_id = app.state.agent.memory.create_run("debug failing run")
            app.state.agent.memory.save_step(run_id, {
                "id": 1,
                "title": "run tests",
                "tool": "test.run",
                "args": {"runner": "pytest"},
                "status": "failed",
                "result": None,
                "error": "AssertionError",
                "started_at": "2026-04-23T00:00:00",
                "completed_at": "2026-04-23T00:00:01",
            })
            app.state.agent.memory.save_artifact(run_id, "step_1_stdout", "trace log", step_id=1, artifact_type="log")
            response = client.get(f"/runs/{run_id}/forensics")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["run_id"], run_id)
            self.assertIn("forensics", response.json())

            dashboard = client.get("/dashboard")
            self.assertEqual(dashboard.status_code, 200)
            self.assertIn("forensics", dashboard.text.lower())


if __name__ == "__main__":
    unittest.main()
