import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from velocity_claw.api.server import create_app
from velocity_claw.config.settings import Settings
from velocity_claw.security.access import ApprovalManager


class ExecutionPolicyApprovalIntelligenceV2Tests(unittest.TestCase):
    def test_approval_manager_explains_requirement(self):
        manager = ApprovalManager(Settings(execution_profile="safe"))
        step = {
            "tool": "patch.apply",
            "args": {"path": "sample.py"},
        }
        explanation = manager.explain_requirement(step, "safe")
        self.assertTrue(explanation["required"])
        self.assertEqual(explanation["profile"], "safe")
        self.assertEqual(explanation["tool"], "patch.apply")
        self.assertEqual(explanation["risk_level"], "high")
        self.assertTrue(explanation["triggers"])

    def test_approvals_explain_route(self):
        workspace = tempfile.mkdtemp()
        db_path = str(Path(workspace) / "memory.db")
        settings = Settings(workspace_root=workspace, memory_db_path=db_path)
        with patch("velocity_claw.api.server.load_settings", return_value=settings):
            app = create_app()
            client = TestClient(app)
            response = client.post(
                "/approvals/explain",
                json={
                    "step": {"tool": "shell.run", "args": {"command": "echo hi"}},
                    "profile_name": "dev",
                },
            )
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertTrue(payload["required"])
            self.assertEqual(payload["tool"], "shell.run")
            self.assertEqual(payload["profile"], "dev")
            self.assertIn("triggers", payload)

    def test_dashboard_shows_richer_pending_approval_columns(self):
        workspace = tempfile.mkdtemp()
        db_path = str(Path(workspace) / "memory.db")
        settings = Settings(workspace_root=workspace, memory_db_path=db_path)
        with patch("velocity_claw.api.server.load_settings", return_value=settings):
            app = create_app()
            client = TestClient(app)
            run_id = app.state.agent.memory.create_run("patch task")
            app.state.agent.memory.save_step(
                run_id,
                {
                    "id": 1,
                    "title": "apply patch",
                    "tool": "patch.apply",
                    "args": {"path": "sample.py"},
                    "status": "pending_approval",
                    "result": {
                        "required": True,
                        "reason": "Approval required for tool patch.apply under profile safe: safe_profile_sensitive_write_or_exec",
                        "profile": "safe",
                        "tool": "patch.apply",
                        "risk_level": "high",
                        "triggers": ["safe_profile_sensitive_write_or_exec"],
                        "summary": {"tool": "patch.apply", "path": "sample.py", "command": None},
                    },
                    "error": None,
                    "started_at": "2026-04-23T00:00:00",
                    "completed_at": "2026-04-23T00:00:01",
                },
            )
            dashboard = client.get("/dashboard")
            self.assertEqual(dashboard.status_code, 200)
            self.assertIn("Pending approvals", dashboard.text)
            self.assertIn("Risk", dashboard.text)
            self.assertIn("Triggers", dashboard.text)
            self.assertIn("high", dashboard.text)


if __name__ == "__main__":
    unittest.main()
