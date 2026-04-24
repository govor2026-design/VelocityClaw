import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from velocity_claw.api.ops_console import build_operations_console
from velocity_claw.api.server import create_app
from velocity_claw.config.settings import Settings


class DashboardOperationsConsoleV3Tests(unittest.TestCase):
    def test_build_operations_console_shape(self):
        snapshot = build_operations_console(
            release_state={"readiness": "ready", "score": 8, "total_checks": 10, "blocking_issues": [], "warnings": ["x"]},
            queue_jobs=[{"status": "running"}, {"status": "failed"}, {"status": "cancelled"}],
            approvals=[{"step_id": 1}],
            provider_observability={"summary": {"route_count": 3, "fallback_successes": 1, "failed_routes": 1}},
            last_failed={"run_id": "r1", "task": "demo", "status": "failed"},
            metrics={"queue_total": 3},
            active_workers=1,
            max_concurrency=2,
        )
        self.assertEqual(snapshot["status"], "ok")
        self.assertEqual(snapshot["queue"]["running"], 1)
        self.assertEqual(snapshot["queue"]["failed"], 1)
        self.assertEqual(snapshot["approvals"]["pending"], 1)
        self.assertEqual(snapshot["providers"]["failed_routes"], 1)

    def test_ops_console_route_and_dashboard(self):
        workspace = tempfile.mkdtemp()
        db_path = str(Path(workspace) / "memory.db")
        settings = Settings(workspace_root=workspace, memory_db_path=db_path)
        with patch("velocity_claw.api.server.load_settings", return_value=settings):
            app = create_app()
            client = TestClient(app)
            with patch.object(app.state.release, "evaluate", return_value={
                "readiness": "ready", "score": 8, "total_checks": 10, "blocking_issues": [], "warnings": []
            }), patch.object(app.state.agent.router, "get_router_observability", return_value={
                "summary": {"route_count": 2, "fallback_successes": 1, "failed_routes": 0},
                "recent_route_history": [],
                "providers": {}
            }), patch.object(app.state.agent.router, "get_provider_health", return_value={}):
                response = client.get("/ops/console")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["status"], "ok")
                self.assertIn("queue", response.json())

                dashboard = client.get("/dashboard")
                self.assertEqual(dashboard.status_code, 200)
                self.assertIn("Operations console", dashboard.text)
                self.assertIn("/ops/console", dashboard.text)


if __name__ == "__main__":
    unittest.main()
