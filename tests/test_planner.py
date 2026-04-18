import unittest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from velocity_claw.config.settings import Settings
from velocity_claw.planner.planner import Planner, Plan, PlanStep
from velocity_claw.models.router import ModelRouter


class PlannerTests(unittest.TestCase):
    def setUp(self):
        self.settings = Settings()
        self.router = ModelRouter(self.settings)
        self.planner = Planner(self.router)

    def test_parse_valid_plan(self):
        response = '''{"task": "test", "steps": [{"id": 1, "title": "step1", "tool": "fs.read", "args": {"path": "file.txt"}, "expected_output": "content"}]}'''
        plan = self.planner._parse_plan(response)
        self.assertIsInstance(plan, Plan)
        self.assertEqual(plan.task, "test")
        self.assertEqual(len(plan.steps), 1)

    def test_parse_invalid_plan(self):
        response = "invalid json"
        with self.assertRaises(ValueError):
            self.planner._parse_plan(response)


if __name__ == "__main__":
    unittest.main()