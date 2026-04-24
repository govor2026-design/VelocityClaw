import tempfile
import unittest
from pathlib import Path

from velocity_claw.config.settings import Settings
from velocity_claw.core.agent import VelocityClawAgent
from velocity_claw.models.router import ModelRouter
from velocity_claw.planner.planner import Planner


class PlannerMemoryCouplingV2Tests(unittest.TestCase):
    def test_agent_builds_richer_planning_context(self):
        workspace = tempfile.mkdtemp()
        db_path = str(Path(workspace) / "memory.db")
        agent = VelocityClawAgent(Settings(workspace_root=workspace, memory_db_path=db_path))

        run1 = agent.memory.create_run("fix login")
        agent.memory.save_step(run1, {
            "id": 1,
            "title": "run tests",
            "tool": "test.run",
            "args": {},
            "status": "failed",
            "result": None,
            "error": "boom",
            "started_at": "2026-04-24T00:00:00",
            "completed_at": "2026-04-24T00:00:01",
        })
        agent.memory.update_run_status(run1, "failed")

        run2 = agent.memory.create_run("fix login")
        agent.memory.save_step(run2, {
            "id": 1,
            "title": "run tests again",
            "tool": "test.run",
            "args": {},
            "status": "failed",
            "result": None,
            "error": "boom",
            "started_at": "2026-04-24T00:01:00",
            "completed_at": "2026-04-24T00:01:01",
        })
        agent.memory.update_run_status(run2, "failed")

        agent.memory.save_step(run2, {
            "id": 2,
            "title": "dangerous deploy",
            "tool": "shell.run",
            "args": {"command": "echo hi"},
            "status": "pending_approval",
            "result": {"risk_level": "high"},
            "error": None,
            "started_at": "2026-04-24T00:02:00",
            "completed_at": "2026-04-24T00:02:01",
        })

        context = agent._build_planning_context({})["planning_context"]
        self.assertIn("fix login", context["repeated_failed_tasks"])
        self.assertEqual(context["approval_pressure"]["pending_count"], 1)
        self.assertIn("last_failed_report_summary", context)
        self.assertIn("recent_failure_pattern", context)

    def test_planner_prompt_consumes_memory_signals(self):
        planner = Planner(ModelRouter(Settings()))
        prompt = planner._build_plan_prompt("fix login", {
            "planning_context": {
                "recent_failed_tasks": ["fix login"],
                "repeated_failed_tasks": ["fix login"],
                "last_failed_report_summary": "Run failed in test.run stage.",
                "recent_failure_pattern": {"title": "run tests", "tool": "test.run"},
                "approval_pressure": {"pending_count": 2, "recent_titles": ["deploy"]},
            }
        })
        self.assertIn("Repeated failed tasks", prompt)
        self.assertIn("Last failed run report summary", prompt)
        self.assertIn("Recent failure pattern", prompt)
        self.assertIn("Approval pressure", prompt)


if __name__ == "__main__":
    unittest.main()
