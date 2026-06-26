from pathlib import Path
from typing import Dict, List

from velocity_claw.models.router import ModelRouter
from velocity_claw.logs.logger import get_logger
from velocity_claw.tools.fs import FileSystemTool
from velocity_claw.tools.shell import ShellTool
from velocity_claw.tools.git import GitTool
from velocity_claw.tools.http import HTTPTool
from velocity_claw.tools.patch import PatchEngine
from velocity_claw.tools.code_nav import CodeNavigationTool
from velocity_claw.tools.test_runner import TestRunnerTool
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
        self.patch = PatchEngine(self.settings)
        self.code_nav = CodeNavigationTool(self.settings)
        self.test_runner = TestRunnerTool(self.settings)
        self.security = SecurityManager(self.settings)

    def _get_profile(self, tool: str) -> AccessProfile:
        if tool in ["http.get", "http.post"]:
            return self.security.get_profile("network_allowlist")
        if tool in ["git.run", "git.inspect"]:
            return self.security.get_profile("git_safe")
        if tool in ["fs.write", "fs.append", "fs.replace", "shell.run", "patch.apply", "test.run"]:
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
        base_result = {"id": step_id, "title": title, "tool": tool, "args": args}
        try:
            profile = self._get_profile(tool)
            result = await self._execute_tool(tool, args, profile)
            if tool == "test.run" and isinstance(result, dict):
                runner_status = result.get("status")
                if runner_status not in {"passed", "simulated"}:
                    return {
                        **base_result,
                        "status": "failed",
                        "result": result,
                        "error": f"test_run_{runner_status or 'failed'}",
                    }
            simulated = isinstance(result, dict) and result.get("status") == "simulated"
            if simulated:
                self.logger.info("Dry-run simulated step %s with tool %s", step_id, tool)
            return {
                **base_result,
                "status": "success",
                "result": result,
                "error": None,
                "simulated": simulated,
            }
        except Exception as exc:
            self.logger.exception("Step %s failed: %s", step_id, exc)
            return {**base_result, "status": "failed", "result": None, "error": str(exc), "simulated": False}

    def _dry_run_enabled(self, args: Dict) -> bool:
        return bool(self.settings.dry_run or args.get("dry_run") is True)

    def _display_path(self, resolved: Path) -> str:
        try:
            return str(resolved.relative_to(self.fs.workspace_root)) or "."
        except ValueError:
            return str(resolved)

    def _validate_content_size(self, content: str) -> int:
        encoded_size = len(str(content).encode("utf-8"))
        if encoded_size > self.settings.max_file_size:
            raise ValueError(f"Content too large: {encoded_size}")
        return encoded_size

    def _simulate_file_action(self, tool: str, args: Dict) -> dict:
        resolved = self.fs.validate_path(args["path"])
        before_size = resolved.stat().st_size if resolved.exists() else 0

        if tool == "fs.write":
            after_size = self._validate_content_size(args["content"])
        elif tool == "fs.append":
            append_size = self._validate_content_size(args["content"])
            after_size = before_size + append_size
            if after_size > self.settings.max_file_size:
                raise ValueError("File would exceed size limit")
        elif tool == "fs.replace":
            current = self.fs.read(args["path"])
            old_string = args["old_string"]
            if old_string not in current:
                raise ValueError(f"Old string not found in {args['path']}")
            updated = current.replace(old_string, args["new_string"], 1)
            after_size = self._validate_content_size(updated)
        else:
            raise ValueError(f"Unsupported dry-run file action: {tool}")

        return {
            "status": "simulated",
            "dry_run": True,
            "validated": True,
            "action": tool,
            "path": self._display_path(resolved),
            "exists": resolved.exists(),
            "bytes_before": before_size,
            "bytes_after": after_size,
            "would_change": before_size != after_size or tool == "fs.replace",
        }

    @staticmethod
    def _simulated_action(tool: str, **details) -> dict:
        return {
            "status": "simulated",
            "dry_run": True,
            "validated": True,
            "action": tool,
            **details,
        }

    async def _execute_tool(self, tool: str, args: Dict, profile: AccessProfile):
        dry_run = self._dry_run_enabled(args)
        if tool == "fs.read":
            return self.fs.read(args["path"])
        if tool in {"fs.write", "fs.append", "fs.replace"}:
            if dry_run:
                return self._simulate_file_action(tool, args)
            if tool == "fs.write":
                return self.fs.write(args["path"], args["content"])
            if tool == "fs.append":
                return self.fs.append(args["path"], args["content"])
            return self.fs.replace(args["path"], args["old_string"], args["new_string"])
        if tool == "patch.preview":
            return self.patch.preview(args["patch"])
        if tool == "patch.apply":
            result = self.patch.apply(args["patch"], dry_run=dry_run)
            if dry_run:
                return {"status": "simulated", "dry_run": True, "validated": True, "action": tool, **result}
            return result
        if tool == "code.find_symbol":
            return self.code_nav.find_symbol(args["name"], args.get("kind"))
        if tool == "code.read_symbol":
            return self.code_nav.read_symbol(args["path"], args["name"], args["kind"])
        if tool == "code.read_lines":
            return self.code_nav.read_lines(args["path"], args["start_line"], args["end_line"], args.get("context_lines", 0))
        if tool == "code.list_imports":
            return self.code_nav.list_imports(args["path"])
        if tool == "code.find_references":
            return self.code_nav.find_references(args["name"], path=args.get("path"), limit=args.get("limit", 200))
        if tool == "code.find_routes":
            return self.code_nav.find_routes(path=args.get("path"), route=args.get("route"), method=args.get("method"))
        if tool == "test.run":
            return self.test_runner.run(
                args["runner"],
                target=args.get("target"),
                timeout=args.get("timeout", self.settings.command_timeout),
                extra_args=args.get("extra_args"),
                dry_run=dry_run,
                keyword=args.get("keyword"),
                marker=args.get("marker"),
                nodeid=args.get("nodeid"),
                cwd=args.get("cwd"),
            )
        if tool == "shell.run":
            self.security.validate_command(args["command"], profile)
            if not self.settings.shell_enabled:
                raise RuntimeError("Shell execution is disabled")
            if dry_run:
                argv = self.shell.validate_command(args["command"])
                cwd = self.shell.validate_cwd(args.get("cwd"))
                return self._simulated_action(tool, command=args["command"], argv=argv, cwd=str(cwd))
            return self.shell.run_command(args["command"], args.get("cwd"), timeout=self.settings.command_timeout)
        if tool == "git.inspect":
            return self.git.inspect_repo(args.get("cwd"), timeout=args.get("timeout", self.settings.command_timeout))
        if tool == "git.run":
            self.security.validate_git_command(args["command"], profile)
            if not self.settings.git_enabled:
                raise RuntimeError("Git operations disabled")
            if dry_run:
                argv = self.git.validate_git_command(args["command"])
                cwd = self.git.validate_repo_root(args.get("cwd"))
                return self._simulated_action(tool, command=args["command"], argv=argv, cwd=str(cwd))
            return self.git.run_git_command(args["command"], args.get("cwd"), timeout=self.settings.command_timeout)
        if tool == "http.get":
            self.security.validate_url(args["url"], profile)
            return await self.http.get(args["url"], headers=args.get("headers"), params=args.get("params"))
        if tool == "http.post":
            self.security.validate_url(args["url"], profile)
            if dry_run:
                return self._simulated_action(tool, url=args["url"], payload_present=bool(args.get("data")))
            return await self.http.post(args["url"], args.get("data", {}), headers=args.get("headers"))
        if tool == "analysis":
            response = await self.router.route("analysis", args["prompt"])
            return response.get("text", "") if isinstance(response, dict) else str(response)
        raise ValueError(f"Unknown tool: {tool}")

    def _extract_summary(self, results: List[Dict]) -> str:
        success = [result for result in results if result["status"] == "success"]
        simulated = [result for result in results if result.get("simulated")]
        if not results:
            return "Нет шагов."
        return f"Выполнено {len(success)} из {len(results)} шагов; симулировано {len(simulated)}."
