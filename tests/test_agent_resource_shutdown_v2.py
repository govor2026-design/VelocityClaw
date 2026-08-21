import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from velocity_claw.core.agent import VelocityClawAgent


def test_agent_close_releases_router_session() -> None:
    close = AsyncMock()
    agent = object.__new__(VelocityClawAgent)
    agent.router = SimpleNamespace(close=close)

    asyncio.run(agent.close())

    close.assert_awaited_once_with()
