import asyncio
from typing import Dict, Optional
from velocity_claw.config.settings import Settings
from velocity_claw.logs.logger import get_logger
from velocity_claw.planner.planner import Planner
from velocity_claw.executor.executor import Executor
from velocity_claw.models.router import ModelRouter
from velocity_claw.memory.store import MemoryStore
from velocity_claw.security.policy import SecurityManager


class VelocityClawAgent:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.logger = get_logger("velocity_claw.agent")
        self.router = ModelRouter(settings)
        self.planner = Planner(self.router, self.logger)
        self.executor = Executor(self.router, self.logger, settings)
        self.memory = MemoryStore(settings)
        self.security = SecurityManager(
            safe_mode=settings.safe_mode,
            dev_mode=settings.dev_mode,
            trusted_mode=settings.trusted_mode,
        )

    async def run_task(self, task: str, context: Optional[Dict] = None) -> Dict:
        self.logger.info("Velocity Claw received task: %s", task)
        context = context or {}
        if self.settings.memory_enabled:
            self.memory.save_task_history(task)

        plan = await self.planner.create_plan(task, context)
        result = await self.executor.execute_plan(plan, context)
        report = {
            "task": task,
            "status": result.get("status", "unknown"),
            "summary": result.get("summary", ""),
            "plan": plan,
        }

        if self.settings.memory_enabled:
            self.memory.save_task_result(task, report)

        return report

    def get_status(self) -> Dict:
        return {
            "status": "ready",
            "env": self.settings.env,
            "safe_mode": self.settings.safe_mode,
            "trusted_mode": self.settings.trusted_mode,
            "memory_enabled": self.settings.memory_enabled,
        }

    def reset_context(self) -> Dict:
        self.memory.clear_short_term()
        return {"status": "context reset"}
