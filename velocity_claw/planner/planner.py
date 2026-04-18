import asyncio
from typing import Dict, List
from velocity_claw.models.router import ModelRouter
from velocity_claw.logs.logger import get_logger


class Planner:
    def __init__(self, router: ModelRouter, logger=None):
        self.router = router
        self.logger = logger or get_logger("velocity_claw.planner")

    async def create_plan(self, task: str, context: Dict = None) -> Dict:
        self.logger.info("Creating plan for task")
        context = context or {}
        prompt = self._build_plan_prompt(task, context)
        response = await self.router.route("planning", prompt)
        steps = self._parse_plan(response)
        return {
            "task": task,
            "steps": steps,
            "analysis": response,
        }

    def _build_plan_prompt(self, task: str, context: Dict) -> str:
        instructions = [
            "Ты агент Velocity Claw.",
            "Разбей задачу на логические этапы и предложи порядок выполнения.",
            "Укажи краткие шаги с понятными целями.",
            f"Задача: {task}",
        ]
        if context.get("project_root"):
            instructions.append(f"Проект: {context['project_root']}")
        return "\n".join(instructions)

    def _parse_plan(self, response: str) -> List[Dict]:
        lines = [line.strip() for line in response.splitlines() if line.strip()]
        steps = []
        for index, line in enumerate(lines, 1):
            if line.lower().startswith("шаг") or line[0].isdigit():
                steps.append({"id": index, "title": line, "status": "pending"})
            elif len(steps) < 1:
                steps.append({"id": index, "title": line, "status": "pending"})
        if not steps:
            steps = [{"id": 1, "title": response.strip(), "status": "pending"}]
        return steps
