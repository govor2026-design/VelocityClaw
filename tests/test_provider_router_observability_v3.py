import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from velocity_claw.api.server import create_app
from velocity_claw.config.settings import Settings
from velocity_claw.models.router import ModelRouter


class ProviderRouterObservabilityV3Tests(unittest.TestCase):
    def test_router_observability_summary(self):
        router = ModelRouter(Settings())
        router.route_history = [
            {
                "task_type": "planning",
                "attempts": [{"provider": "openai", "status": "failed"}, {"provider": "ollama", "status": "success"}],
                "selected_provider": "ollama",
                "status": "success",
            },
            {
                "task_type": "analysis",
                "attempts": [{"provider": "openai", "status": "failed"}],
                "selected_provider": None,
                "status": "failed",
            },
        ]
        snapshot = router.get_router_observability()
        self.assertIn("providers", snapshot)
        self.assertIn("recent_route_history", snapshot)
        self.assertEqual(snapshot["summary"]["route_count"], 2)
        self.assertEqual(snapshot["summary"]["fallback_successes"], 1)
        self.assertEqual(snapshot["summary"]["failed_routes"], 1)

    def test_provider_observability_route_and_dashboard(self):
        workspace = tempfile.mkdtemp()
        db_path = str(Path(workspace) / "memory.db")
        settings = Settings(workspace_root=workspace, memory_db_path=db_path)
        with patch("velocity_claw.api.server.load_settings", return_value=settings):
            app = create_app()
            client = TestClient(app)
            with patch.object(app.state.agent.router, "get_router_observability", return_value={
                "providers": {"openai": {"requests": 2, "successes": 1, "failures": 1, "in_cooldown": False, "last_task_type": "planning", "last_error": None}},
                "recent_route_history": [{"task_type": "planning", "status": "success", "selected_provider": "openai", "attempts": [{"provider": "openai", "status": "success"}]}],
                "summary": {"route_count": 1, "fallback_successes": 0, "failed_routes": 0},
            }), patch.object(app.state.agent.router, "get_provider_health", return_value={
                "openai": {"requests": 2, "successes": 1, "failures": 1, "in_cooldown": False, "last_task_type": "planning", "last_error": None}
            }):
                response = client.get("/providers/observability")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["summary"]["route_count"], 1)

                dashboard = client.get("/dashboard")
                self.assertEqual(dashboard.status_code, 200)
                self.assertIn("Provider/router observability", dashboard.text)
                self.assertIn("Recent route history", dashboard.text)


if __name__ == "__main__":
    unittest.main()
