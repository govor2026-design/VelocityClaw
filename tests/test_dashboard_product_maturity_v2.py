import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from velocity_claw.api.server import create_app
from velocity_claw.config.settings import Settings


class DashboardProductMaturityV2Tests(unittest.TestCase):
    def test_provider_health_and_dashboard_routes(self):
        workspace = tempfile.mkdtemp()
        db_path = str(Path(workspace) / "memory.db")
        settings = Settings(workspace_root=workspace, memory_db_path=db_path)

        with patch("velocity_claw.api.server.load_settings", return_value=settings):
            app = create_app()
            client = TestClient(app)

            health = client.get("/providers/health")
            self.assertEqual(health.status_code, 200)
            self.assertIn("providers", health.json())

            dashboard = client.get("/dashboard")
            self.assertEqual(dashboard.status_code, 200)
            self.assertIn("Provider health", dashboard.text)

    def test_run_planning_context_endpoint(self):
        workspace = tempfile.mkdtemp()
        db_path = str(Path(workspace) / "memory.db")
        settings = Settings(workspace_root=workspace, memory_db_path=db_path)

        with patch("velocity_claw.api.server.load_settings", return_value=settings):
            app = create_app()
            client = TestClient(app)
            run_id = app.state.agent.memory.create_run("analyze repo")
            app.state.agent.memory.save_artifact(
                run_id,
                "planning_context",
                '{"project_root": ".", "planning_context": {"recent_run_tasks": ["analyze repo"]}}',
                artifact_type="planning_context",
            )

            response = client.get(f"/runs/{run_id}/planning-context")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["run_id"], run_id)
            self.assertIn("planning_context", response.json())


if __name__ == "__main__":
    unittest.main()
