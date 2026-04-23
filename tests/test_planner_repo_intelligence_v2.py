import tempfile
import unittest
from pathlib import Path

from velocity_claw.config.settings import Settings
from velocity_claw.core.agent import VelocityClawAgent
from velocity_claw.memory.store import MemoryStore
from velocity_claw.models.router import ModelRouter
from velocity_claw.planner.planner import Planner


class PlannerRepoIntelligenceV2Tests(unittest.IsolatedAsyncioTestCase):
    async def test_memory_builds_planning_context(self):
        workspace = tempfile.mkdtemp()
        db_path = str(Path(workspace) / "memory.db")
        store = MemoryStore(Settings(workspace_root=workspace, memory_db_path=db_path))
        run_id = store.create_run("fix tests")
        store.update_run_status(run_id, "failed")
        store.save_project_fact("language", {"name": "python"})
        store.save_project_note("convention", "use pytest")
        context = store.build_planning_context()
        self.assertIn("project_facts", context)
        self.assertIn("recent_notes", context)
        self.assertEqual(context["project_facts"]["language"]["name"], "python")
        self.assertTrue(context["last_failed_run"])

    async def test_planner_prompt_includes_planning_context(self):
        settings = Settings()
        planner = Planner(ModelRouter(settings))
        prompt = planner._build_plan_prompt(
            "fix tests",
            {
                "project_root": "/repo",
                "planning_context": {
                    "project_facts": {"language": {"name": "python"}},
                    "recent_notes": [{"note_type": "convention", "content": "use pytest"}],
                    "recent_run_tasks": ["fix tests"],
                    "recent_failed_tasks": ["fix tests"],
                    "last_failed_run": {"task": "fix tests", "status": "failed"},
                },
            },
        )
        self.assertIn("Project facts", prompt)
        self.assertIn("Recent failed tasks", prompt)
        self.assertIn("Last failed run", prompt)

    async def test_agent_injects_planning_context_automatically(self):
        workspace = tempfile.mkdtemp()
        db_path = str(Path(workspace) / "memory.db")
        settings = Settings(workspace_root=workspace, memory_db_path=db_path)
        agent = VelocityClawAgent(settings)
        captured = {}

        async def fake_plan(task, context=None):
            captured["context"] = context
            return {"task": task, "steps": []}

        agent.planner.create_plan = fake_plan
        result = await agent.run_task("analyze repo")
        self.assertEqual(result["status"], "failed")
        self.assertIn("planning_context", captured["context"])
        self.assertEqual(captured["context"]["project_root"], workspace)


if __name__ == "__main__":
    unittest.main()
