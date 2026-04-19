import unittest

from velocity_claw.api.server import create_app


class DashboardV2Tests(unittest.TestCase):
    def test_app_exposes_profile_manager(self):
        app = create_app()
        self.assertTrue(hasattr(app.state, "profiles"))

    def test_active_profile_matrix_contains_capabilities(self):
        app = create_app()
        matrix = app.state.profiles.get_capability_matrix()
        self.assertIn("capabilities", matrix)
        self.assertIn("approval_workflow", matrix["capabilities"])
        self.assertIn("patch_engine", matrix["capabilities"])


if __name__ == "__main__":
    unittest.main()
