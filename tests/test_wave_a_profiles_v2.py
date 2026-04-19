import unittest

from velocity_claw.api.server import create_app
from velocity_claw.config.settings import Settings
from velocity_claw.security.access import ExecutionProfileManager


class ExecutionProfilesV2Tests(unittest.TestCase):
    def test_capability_matrix_has_expected_profiles(self):
        settings = Settings(execution_profile="safe")
        manager = ExecutionProfileManager(settings)
        profiles = manager.list_profiles()
        self.assertIn("safe", profiles)
        self.assertIn("dev", profiles)
        self.assertIn("owner", profiles)

    def test_active_profile_matrix(self):
        settings = Settings(execution_profile="dev")
        manager = ExecutionProfileManager(settings)
        matrix = manager.get_capability_matrix()
        self.assertEqual(matrix["profile"], "dev")
        self.assertTrue(matrix["capabilities"]["patch_engine"])
        self.assertTrue(matrix["capabilities"]["shell"])

    def test_explain_tool_access(self):
        settings = Settings(execution_profile="safe")
        manager = ExecutionProfileManager(settings)
        info = manager.explain_tool_access("patch.apply")
        self.assertEqual(info["profile"], "safe")
        self.assertFalse(info["allowed"])

    def test_api_has_profile_manager(self):
        app = create_app()
        self.assertTrue(hasattr(app.state, "profiles"))


if __name__ == "__main__":
    unittest.main()
