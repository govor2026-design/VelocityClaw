import unittest
from velocity_claw.config.settings import load_settings
from velocity_claw.core.agent import VelocityClawAgent


class AgentSmokeTest(unittest.TestCase):
    def test_agent_initializes(self):
        settings = load_settings()
        agent = VelocityClawAgent(settings=settings)
        self.assertEqual(agent.get_status()["status"], "ready")


if __name__ == "__main__":
    unittest.main()
