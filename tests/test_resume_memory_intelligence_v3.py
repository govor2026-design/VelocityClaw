import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from velocity_claw.api.server import create_app
from velocity_claw.config.settings import Settings
from velocity_claw.memory.store import MemoryStore


class ResumeMemoryIntelligenceV3Tests(unittest.IsolatedAsyncioTestCase):
    async def test_memory_builds_resume_context_with_fix_attempts(self):
        workspace = tempfile.mkdtemp()
        db_path = str(Path(workspace) / "memory.db")
        store = MemoryStore(Settings(workspace_root=workspace, memory_db_path=db_path))
        run_id = store.create_run("fix tests")
        store.update_run_status(run_id, "failed")
        store.save_fix_attempt(run_id, 1, {"summary": "tried patch A"})
        store.save_project_note("note", "watch flaky tests")
        ctx = store.build_resume_context("fix tests")
        self.assertEqual(ctx["task"], "fix tests")
        self.assertTrue(ctx["related_runs"])
        self.assertTrue(ctx["recent_fix_attempts"])
        self.assertTrue(ctx["recent_notes"])

    async def test_agent_persists_resume_context_artifact(self):
        workspace = tempfile.mkdtemp()
        db_path = str(Path(workspace) / "memory.db")
        settings = Settings(workspace_root=workspace, memory_db_path=db_path)

        with patch("velocity_claw.api.server.load_settings", return_value=settings):
            app = create_app()
            agent = app.state.agent

            async def fake_plan(task, context=None):
                return {"task": task, "steps": []}

            agent.planner.create_plan = fake_plan
            result = await agent.run_task("analyze repo")
            self.assertEqual(result["status"], "failed")
            run = agent.memory.load_run(result["run_id"])
            names = [a["name"] for a in run["artifacts"]]
            self.assertIn("resume_context", names)

    async def test_resume_context_routes(self):
        workspace = tempfile.mkdtemp()
        db_path = str(Path(workspace) / "memory.db")
        settings = Settings(workspace_root=workspace, memory_db_path=db_path)

        with patch("velocity_claw.api.server.load_settings", return_value=settings):
            app = create_app()
            client = TestClient(app)
            run_id = app.state.agent.memory.create_run("fix tests")
            app.state.agent.memory.save_fix_attempt(run_id, 1, {"summary": "tried patch A"})
            app.state.agent.memory.save_artifact(
                run_id,
                "resume_context",
                '{"task": "fix tests", "recent_fix_attempts": [{"attempt_no": 1}]}',
                artifact_type="resume_context",
            )

            response = client.get(f"/runs/{run_id}/resume-context")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["run_id"], run_id)
            self.assertIn("resume_context", response.json())

            dashboard = client.get("/dashboard")
            self.assertEqual(dashboard.status_code, 200)
            self.assertIn("Resume context", dashboard.text)


if __name__ == "__main__":
    unittest.main()
