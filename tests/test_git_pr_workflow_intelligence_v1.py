import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from velocity_claw.api.server import create_app
from velocity_claw.config.settings import Settings
from velocity_claw.tools.git import GitTool


class GitPrWorkflowIntelligenceV1Tests(unittest.TestCase):
    def test_git_tool_inspect_repo_summary(self):
        workspace = tempfile.mkdtemp()
        settings = Settings(workspace_root=workspace)
        git = GitTool(settings)

        with patch.object(git, "run_git_command") as run_git_command:
            run_git_command.side_effect = [
                {"code": 0, "stdout": "main", "stderr": ""},
                {"code": 0, "stdout": " M file.py", "stderr": ""},
                {"code": 0, "stdout": "abc123 commit one\ndef456 commit two", "stderr": ""},
                {"code": 0, "stdout": " file.py | 2 +-", "stderr": ""},
            ]
            summary = git.inspect_repo()

        self.assertEqual(summary["branch"], "main")
        self.assertFalse(summary["is_clean"])
        self.assertEqual(len(summary["recent_commits"]), 2)
        self.assertIn("file.py", summary["diff_stat"])

    def test_git_summary_route_and_dashboard(self):
        workspace = tempfile.mkdtemp()
        db_path = str(Path(workspace) / "memory.db")
        settings = Settings(workspace_root=workspace, memory_db_path=db_path)

        with patch("velocity_claw.api.server.load_settings", return_value=settings):
            app = create_app()
            client = TestClient(app)
            with patch.object(app.state.agent.executor.git, "inspect_repo", return_value={
                "branch": "main",
                "is_clean": True,
                "status_short": "",
                "recent_commits": ["abc123 init"],
                "diff_stat": "",
                "repo_root": workspace,
            }):
                response = client.get("/git/summary")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["branch"], "main")

                dashboard = client.get("/dashboard")
                self.assertEqual(dashboard.status_code, 200)
                self.assertIn("Git summary", dashboard.text)


if __name__ == "__main__":
    unittest.main()
