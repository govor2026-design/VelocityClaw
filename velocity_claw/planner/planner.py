import json
import re
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



def extract_json_payload(raw: str):
    text = raw.strip()

    fence_match = re.search(r"```(?:json)?\s*(\{.*\}|\[.*\])\s*```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    obj_start = text.find("{")
    obj_end = text.rfind("}")
    if obj_start != -1 and obj_end != -1 and obj_end > obj_start:
        candidate = text[obj_start:obj_end + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    arr_start = text.find("[")
    arr_end = text.rfind("]")
    if arr_start != -1 and arr_end != -1 and arr_end > arr_start:
        candidate = text[arr_start:arr_end + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    raise ValueError("planner_invalid_json_payload")


class Planner:
    def __init__(self, router: ModelRouter, logger=None):
        self.router = router
        self.logger = logger or get_logger("velocity_claw.planner")

    async def create_plan(self, task: str, context: Dict = None) -> Dict:
        self.logger.info("Creating plan for task")
        context = context or {}
        prompt = self._build_plan_prompt(task, context)
        response = await self.router.route("planning", prompt)
        text = response.get("text", "") if isinstance(response, dict) else str(response)
        plan = self._parse_plan(text)
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
            data = extract_json_payload(response)
            return Plan(**data)
        except (json.JSONDecodeError, ValidationError, ValueError) as e:
            self.logger.error("Failed to parse plan: %s", e)
            raise ValueError(f"Invalid plan format: {e}")
