from velocity_claw.config.settings import load_settings
from velocity_claw.core.agent import VelocityClawAgent


def start_agent():
    settings = load_settings()
    agent = VelocityClawAgent(settings=settings)
    return agent
