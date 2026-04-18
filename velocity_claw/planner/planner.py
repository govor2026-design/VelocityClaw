import asyncio
import json
from typing import Dict, List
from pydantic import BaseModel, ValidationError
from velocity_claw.models.router import ModelRouter
from velocity_claw.logs.logger import get_logger


class PlanStep(BaseModel):
    id: int
    title: str
    tool: str
    args: Dict
    expected_output: str


class Plan(BaseModel):
    task: str
    steps: List[PlanStep]


class Planner:
    def __init__(self, router: ModelRouter, logger=None):
        self.router = router
        self.logger = logger or get_logger("velocity_claw.planner")

    async def create_plan(self, task: str, context: Dict = None) -> Dict:
        self.logger.info("Creating plan for task")
        context = context or {}
        prompt = self._build_plan_prompt(task, context)
        response = await self.router.route("planning", prompt)
        plan = self._parse_plan(response)
        return plan.dict()

    def _build_plan_prompt(self, task: str, context: Dict) -> str:
        instructions = [
            "Ты агент Velocity Claw.",
            "Разбей задачу на логические этапы.",
            "Для каждого шага укажи:",
            "- id: уникальный номер",
            "- title: краткое описание",
            "- tool: инструмент (fs.read, fs.write, git.run, shell.run, http.get, analysis)",
            "- args: аргументы для инструмента",
            "- expected_output: ожидаемый результат",
            "Верни только валидный JSON без лишнего текста.",
            f"Задача: {task}",
        ]
        if context.get("project_root"):
            instructions.append(f"Проект: {context['project_root']}")
        return "\n".join(instructions)

    def _parse_plan(self, response: str) -> Plan:
        try:
            # Try to extract JSON from response
            start = response.find("{")
            end = response.rfind("}") + 1
            if start == -1 or end == 0:
                raise ValueError("No JSON found in response")
            json_str = response[start:end]
            data = json.loads(json_str)
            plan = Plan(**data)
            return plan
        except (json.JSONDecodeError, ValidationError, ValueError) as e:
            self.logger.error(f"Failed to parse plan: {e}")
            raise ValueError(f"Invalid plan format: {e}")
