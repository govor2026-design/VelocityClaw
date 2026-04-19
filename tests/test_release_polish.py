import unittest

from velocity_claw.api.server import create_app
from velocity_claw.core.modes import HIGH_LEVEL_MODES


class ReleasePolishTests(unittest.TestCase):
    def test_app_exposes_queue_and_metrics(self):
        app = create_app()
        self.assertTrue(hasattr(app.state, "queue"))
        self.assertTrue(hasattr(app.state, "metrics"))

    def test_high_level_modes_exist(self):
        self.assertIn("analyze_repo", HIGH_LEVEL_MODES)
        self.assertIn("repair_failed_tests", HIGH_LEVEL_MODES)


if __name__ == "__main__":
    unittest.main()
