from typing import Dict, List
from velocity_claw.models.router import ModelRouter
from velocity_claw.logs.logger import get_logger
from velocity_claw.tools.fs import FileSystemTool
from velocity_claw.tools.shell import ShellTool
from velocity_claw.tools.git import GitTool
from velocity_claw.tools.http import HTTPTool
from velocity_claw.security.policy import SecurityManager, AccessProfile
from velocity_claw.config.settings import Settings


class Executor:
    def __init__(self, router: ModelRouter, logger=None, settings: Settings = None):
        self.router = router
        self.logger = logger or get_logger("velocity_claw.executor")
        self.settings = settings or Settings()
        self.fs = FileSystemTool(self.settings)
        self.shell = ShellTool(self.settings)
        self.git = GitTool(self.settings)
        self.http = HTTPTool(self.settings)
        self.security = SecurityManager(self.settings)

    def _get_profile(self, tool: str) -> AccessProfile:
        if tool in ["http.get", "http.post"]:
            return self.security.get_profile("network_allowlist")
        if tool == "git.run":
            return self.security.get_profile("git_safe")
        if tool in ["fs.write", "fs.append", "fs.replace", "shell.run"]:
            return self.security.get_profile("workspace_write")
        return self.security.get_profile("read_only")

    async def execute_plan(self, plan: Dict, context: Dict = None) -> Dict:
        context = context or {}
        self.logger.info("Executing plan with %d steps", len(plan.get("steps", [])))
        results = []
        for step in plan.get("steps", []):
            result = await self.execute_step(step, context)
            results.append(result)
            if result.get("status") == "failed":
                break
        summary = self._extract_summary(results)
        return {
            "status": "completed" if all(r["status"] == "success" for r in results) else "partial",
            "summary": summary,
            "results": results,
        }

    async def execute_step(self, step: Dict, context: Dict) -> Dict:
        step_id = step.get("id")
        title = step.get("title", "unknown")
        tool = step.get("tool")
        args = step.get("args", {})
        self.logger.info("Executing step %s: %s", step_id, title)
        base_result = {
            "id": step_id,
            "title": title,
            "tool": tool,
            "args": args,
        }
        try:
            profile = self._get_profile(tool)
            result = await self._execute_tool(tool, args, profile)
            return {**base_result, "status": "success", "result": result, "error": None}
        except Exception as e:
            self.logger.error("Step %s failed: %s", step_id, e)
            return {**base_result, "status": "failed", "result": None, "error": str(e)}

    async def _execute_tool(self, tool: str, args: Dict, profile: AccessProfile):
        if tool == "fs.read":
            return self.fs.read(args["path"])
        if tool == "fs.write":
            return self.fs.write(args["path"], args["content"])
        if tool == "fs.append":
            return self.fs.append(args["path"], args["content"])
        if tool == "fs.replace":
            return self.fs.replace(args["path"], args["old_string"], args["new_string"])
        if tool == "shell.run":
            self.security.validate_command(args["command"], profile)
            return self.shell.run_command(args["command"], args.get("cwd"), timeout=self.settings.command_timeout)
        if tool == "git.run":
            self.security.validate_git_command(args["command"], profile)
            return self.git.run_git_command(args["command"], args.get("cwd"), timeout=self.settings.command_timeout)
        if tool == "http.get":
            self.security.validate_url(args["url"], profile)
            return await self.http.get(args["url"], headers=args.get("headers"), params=args.get("params"))
        if tool == "http.post":
            self.security.validate_url(args["url"], profile)
            return await self.http.post(args["url"], args.get("data", {}), headers=args.get("headers"))
        if tool == "analysis":
            response = await self.router.route("analysis", args["prompt"])
            return response.get("text", "") if isinstance(response, dict) else str(response)
        raise ValueError(f"Unknown tool: {tool}")

    def _extract_summary(self, results: List[Dict]) -> str:
        success = [r for r in results if r["status"] == "success"]
        return f"Выполнено {len(success)} из {len(results)} шагов." if results else "Нет шагов."
