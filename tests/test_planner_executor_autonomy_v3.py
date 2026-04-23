import unittest

from velocity_claw.config.settings import Settings
from velocity_claw.models.router import ModelRouter
from velocity_claw.planner.planner import Planner


class PlannerExecutorAutonomyV3Tests(unittest.TestCase):
    def test_planner_prompt_includes_inspection_first_guidance(self):
        planner = Planner(ModelRouter(Settings()))
        prompt = planner._build_plan_prompt(
            "fix failing tests in repo",
            {
                "project_root": "/repo",
                "planning_context": {
                    "recent_failed_tasks": ["fix failing tests"],
                    "recent_notes": [{"note_type": "note", "content": "prefer reproducing tests first"}],
                },
            },
        )
        self.assertIn("inspection-first", prompt)
        self.assertIn("git.inspect", prompt)
        self.assertIn("code.find_symbol", prompt)
        self.assertIn("code.read_symbol", prompt)
        self.assertIn("Не начинай план с patch.apply", prompt)

    def test_planner_prompt_lists_editing_tools_separately(self):
        planner = Planner(ModelRouter(Settings()))
        prompt = planner._build_plan_prompt("implement feature", {})
        self.assertIn("Editing tools", prompt)
        self.assertIn("patch.apply", prompt)
        self.assertIn("fs.write", prompt)
        self.assertIn("shell.run", prompt)


if __name__ == "__main__":
    unittest.main()
