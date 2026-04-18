import asyncio
from typing import Dict, List
from velocity_claw.models.router import ModelRouter
from velocity_claw.logs.logger import get_logger
from velocity_claw.tools.fs import FileSystemTool
from velocity_claw.tools.shell import ShellTool
from velocity_claw.tools.git import GitTool
from velocity_claw.tools.http import HTTPTool
from velocity_claw.tools.editor import EditorTool
from velocity_claw.security.policy import SecurityManager
from velocity_claw.config.settings import Settings


class Executor:
    def __init__(self, router: ModelRouter, logger=None, settings: Settings = None):
        self.router = router
        self.logger = logger or get_logger("velocity_claw.executor")
        self.fs = FileSystemTool()
        self.shell = ShellTool()
        self.git = GitTool()
        self.http = HTTPTool()
        self.editor = EditorTool()
        self.settings = settings
        self.security = SecurityManager(
            safe_mode=settings.safe_mode if settings else True,
            dev_mode=settings.dev_mode if settings else False,
            trusted_mode=settings.trusted_mode if settings else False,
        )

    async def execute_plan(self, plan: Dict, context: Dict = None) -> Dict:
        context = context or {}
        self.logger.info("Executing plan with %d steps", len(plan.get("steps", [])))
        results = []
        for step in plan.get("steps", []):
            result = await self.execute_step(step, context)
            results.append(result)
            if result.get("status") == "failed" and not self.settings.dev_mode:
                break

        summary = self._extract_summary(results)
        return {"status": "completed" if all(r["status"] == "success" for r in results) else "partial", "summary": summary, "results": results}

    async def execute_step(self, step: Dict, context: Dict) -> Dict:
        title = step.get("title", "unknown")
        self.logger.info("Executing step: %s", title)
        tool_choice = self.select_tool(title)
        if tool_choice == "shell":
            return await self._run_shell(title)
        if tool_choice == "git":
            return await self._run_git(title)
        if tool_choice == "http":
            return await self._run_http(title)
        if tool_choice == "edit":
            return await self._run_edit(title)
        return await self._run_analysis(title)

    def select_tool(self, text: str) -> str:
        lowered = text.lower()
        if any(keyword in lowered for keyword in ["git", "commit", "branch", "clone"]):
            return "git"
        if any(keyword in lowered for keyword in ["shell", "command", "bash", "powershell", "run"]):
            return "shell"
        if any(keyword in lowered for keyword in ["http", "api", "request", "fetch"]):
            return "http"
        if any(keyword in lowered for keyword in ["edit", "write", "create file", "update", "modify"]):
            return "edit"
        return "analysis"

    async def _run_shell(self, title: str) -> Dict:
        command = title
        if not self.security.can_execute(command):
            return {"title": title, "status": "failed", "reason": "unsafe command"}
        output = self.shell.run_command(command)
        return {"title": title, "status": "success" if output["code"] == 0 else "failed", "output": output}

    async def _run_git(self, title: str) -> Dict:
        command = title
        if not self.security.can_execute(command):
            return {"title": title, "status": "failed", "reason": "unsafe git operation"}
        output = self.git.run_git_command(command)
        return {"title": title, "status": "success" if output["code"] == 0 else "failed", "output": output}

    async def _run_http(self, title: str) -> Dict:
        prompt = f"Определи HTTP запрос для: {title}"
        response = await self.router.route("fast", prompt)
        return {"title": title, "status": "success", "response": response}

    async def _run_edit(self, title: str) -> Dict:
        return {"title": title, "status": "success", "detail": "edit support available"}

    async def _run_analysis(self, title: str) -> Dict:
        prompt = f"Анализ задачи: {title}"
        response = await self.router.route("analysis", prompt)
        return {"title": title, "status": "success", "analysis": response}

    def _extract_summary(self, results: List[Dict]) -> str:
        success = [r for r in results if r["status"] == "success"]
        return f"Выполнено {len(success)} из {len(results)} шагов." if results else "Нет шагов."
