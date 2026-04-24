import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from velocity_claw.api.server import create_app
from velocity_claw.config.settings import Settings


class ApiContractResponseSchemaHardeningV2Tests(unittest.TestCase):
    def test_read_endpoints_use_stable_envelopes(self):
        workspace = tempfile.mkdtemp()
        db_path = str(Path(workspace) / "memory.db")
        settings = Settings(workspace_root=workspace, memory_db_path=db_path)
        with patch("velocity_claw.api.server.load_settings", return_value=settings):
            app = create_app()
            client = TestClient(app)

            health = client.get("/health")
            self.assertEqual(health.status_code, 200)
            self.assertEqual(health.json()["status"], "ok")
            self.assertIn("metrics", health.json())

            providers = client.get("/providers/health")
            self.assertEqual(providers.status_code, 200)
            self.assertEqual(providers.json()["status"], "ok")
            self.assertIn("providers", providers.json())

            queue = client.get("/queue")
            self.assertEqual(queue.status_code, 200)
            self.assertEqual(queue.json()["status"], "ok")
            self.assertIn("jobs", queue.json())

    def test_run_report_endpoint_exists(self):
        workspace = tempfile.mkdtemp()
        db_path = str(Path(workspace) / "memory.db")
        settings = Settings(workspace_root=workspace, memory_db_path=db_path)
        with patch("velocity_claw.api.server.load_settings", return_value=settings):
            app = create_app()
            client = TestClient(app)
            run_id = app.state.agent.memory.create_run("demo")
            app.state.agent.memory.save_step(run_id, {
                "id": 1,
                "title": "inspect repo",
                "tool": "git.inspect",
                "args": {},
                "status": "success",
                "result": {"ok": True},
                "error": None,
                "started_at": "2026-04-24T00:00:00",
                "completed_at": "2026-04-24T00:00:01",
            })
            report = client.get(f"/runs/{run_id}/report")
            self.assertEqual(report.status_code, 200)
            self.assertEqual(report.json()["status"], "ok")
            self.assertIn("report", report.json())
            self.assertIn("executive_summary", report.json()["report"])


if __name__ == "__main__":
    unittest.main()
