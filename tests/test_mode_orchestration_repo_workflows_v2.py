import unittest

from velocity_claw.core.modes import HIGH_LEVEL_MODES, build_mode_task


class ModeOrchestrationRepoWorkflowsV2Tests(unittest.TestCase):
    def test_mode_task_contains_workflow_and_verification(self):
        task = build_mode_task("fix_bug", "broken login flow")
        self.assertIn("Repo workflow hint:", task)
        self.assertIn("Verification focus:", task)
        self.assertIn("reproduction/inspection", task)
        self.assertIn("Исходная задача: broken login flow", task)

    def test_high_level_modes_have_structured_specs(self):
        for mode, spec in HIGH_LEVEL_MODES.items():
            self.assertIn("goal", spec)
            self.assertIn("workflow", spec)
            self.assertIn("verification", spec)
            self.assertTrue(spec["goal"])
            self.assertTrue(spec["workflow"])
            self.assertTrue(spec["verification"])


if __name__ == "__main__":
    unittest.main()
