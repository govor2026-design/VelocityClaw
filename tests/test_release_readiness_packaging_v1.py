import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from velocity_claw.api.server import create_app
from velocity_claw.config.settings import Settings
from velocity_claw.core.release import ReleaseReadinessEvaluator


class ReleaseReadinessPackagingV1Tests(unittest.TestCase):
    def test_release_evaluator_reports_readiness_shape(self):
        workspace = tempfile.mkdtemp()
        Path(workspace, "README.md").write_text("# Demo\n")
        Path(workspace, "requirements.txt").write_text("fastapi\n")
        Path(workspace, "Dockerfile").write_text("FROM python:3.12-slim\n")
        Path(workspace, ".env.example").write_text("OPENAI_API_KEY=\n")
        Path(workspace, "cli.py").write_text("print('ok')\n")
        (Path(workspace) / "velocity_claw" / "api").mkdir(parents=True)
        (Path(workspace) / "velocity_claw" / "telegram_bot").mkdir(parents=True)
        (Path(workspace) / "tests").mkdir(parents=True)
        Path(workspace, "velocity_claw", "api", "server.py").write_text("app = None\n")
        Path(workspace, "velocity_claw", "telegram_bot", "bot.py").write_text("bot = None\n")
        Path(workspace, "tests", "test_demo.py").write_text("def test_ok():\n    assert True\n")

        evaluator = ReleaseReadinessEvaluator(Settings(workspace_root=workspace))
        result = evaluator.evaluate()
        self.assertIn("readiness", result)
        self.assertIn("checks", result)
        self.assertIn("packaging_targets", result)
        self.assertEqual(result["readiness"], "ready")

    def test_release_readiness_route_and_dashboard(self):
        workspace = tempfile.mkdtemp()
        db_path = str(Path(workspace) / "memory.db")
        settings = Settings(workspace_root=workspace, memory_db_path=db_path)

        with patch("velocity_claw.api.server.load_settings", return_value=settings):
            app = create_app()
            client = TestClient(app)
            with patch.object(app.state.release, "evaluate", return_value={
                "readiness": "ready",
                "score": 8,
                "total_checks": 10,
                "checks": {"readme_present": True},
                "blocking_issues": [],
                "warnings": ["warning"],
                "packaging_targets": {"cli": True, "api": True, "docker": False, "telegram": True},
            }):
                response = client.get("/release/readiness")
                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertEqual(payload["status"], "ok")
                self.assertEqual(payload["release"]["readiness"], "ready")

                dashboard = client.get("/dashboard")
                self.assertEqual(dashboard.status_code, 200)
                self.assertIn("Release readiness", dashboard.text)
                self.assertIn("Score", dashboard.text)


if __name__ == "__main__":
    unittest.main()
