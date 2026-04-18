from datetime import datetime
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
        self.security = SecurityManager(settings)

    def _get_profile_for_tool(self, tool: str) -> str:
        if tool in ["http.get", "http.post"]:
            return "network_allowlist"
        if tool in ["git.run"]:
            return "git_safe"
        if tool in ["fs.write", "fs.append", "fs.replace", "shell.run"]:
            return "workspace_write"
        return "read_only"

    async def run_task(self, task: str, context: Optional[Dict] = None) -> Dict:
        run_id = self.memory.create_run(task)
        self.logger.info("Starting run %s for task: %s", run_id, task)
        try:
            self.logger.info("Run %s: Planning", run_id)
            plan = await self.planner.create_plan(task, context)
            results = []
            for step in plan["steps"]:
                step_id = step["id"]
                self.logger.info("Run %s: Executing step %s", run_id, step_id)
                profile_name = self._get_profile_for_tool(step.get("tool", ""))
                profile = self.security.get_profile(profile_name)
                started_at = datetime.now().isoformat()
                try:
                    if step["tool"] == "shell.run":
                        self.security.validate_command(step["args"].get("command", ""), profile)
                    elif step["tool"] == "fs.read":
                        self.security.validate_path(step["args"].get("path", ""), profile, write=False)
                    elif step["tool"] in ["fs.write", "fs.append", "fs.replace"]:
                        self.security.validate_path(step["args"].get("path", ""), profile, write=True)
                    elif step["tool"] in ["http.get", "http.post"]:
                        self.security.validate_url(step["args"].get("url", ""), profile)
                    elif step["tool"] == "git.run":
                        self.security.validate_git_command(step["args"].get("command", ""), profile)
                except Exception as e:
                    completed_at = datetime.now().isoformat()
                    self.logger.error("Run %s: Security validation failed for step %s: %s", run_id, step_id, e)
                    step_result = {
                        "id": step_id,
                        "title": step["title"],
                        "tool": step.get("tool"),
                        "args": step.get("args", {}),
                        "status": "failed",
                        "result": None,
                        "error": str(e),
                        "started_at": started_at,
                        "completed_at": completed_at,
                    }
                    results.append(step_result)
                    self.memory.save_step(run_id, step_result)
                    break

                step_result = await self.executor.execute_step(step, context or {})
                step_result["started_at"] = started_at
                step_result["completed_at"] = datetime.now().isoformat()
                results.append(step_result)
                self.memory.save_step(run_id, step_result)
                if step_result["status"] == "failed":
                    break

            status = "completed" if results and all(r["status"] == "success" for r in results) else "failed"
            summary = self._build_summary(results)
            self.memory.update_run_status(run_id, status)
            report = {
                "run_id": run_id,
                "task": task,
                "status": status,
                "summary": summary,
                "steps": results,
                "signature": "velocity claw",
            }
            self.logger.info("Run %s completed with status: %s", run_id, status)
            return report
        except Exception as e:
            self.logger.error("Run %s failed: %s", run_id, e)
            self.memory.update_run_status(run_id, "failed")
            raise

    def get_status(self) -> Dict:
        return {
            "status": "ready",
            "env": self.settings.env,
            "safe_mode": self.settings.safe_mode,
            "trusted_mode": self.settings.trusted_mode,
            "memory_enabled": self.settings.memory_enabled,
            "signature": "velocity claw",
        }

    def reset_context(self) -> Dict:
        self.memory.clear_short_term()
        return {"status": "context reset", "signature": "velocity claw"}

    def _build_summary(self, results: list) -> str:
        success_count = sum(1 for r in results if r["status"] == "success")
        total_count = len(results)
        if total_count == 0:
            return "No steps executed."
        return f"Executed {success_count}/{total_count} steps successfully."
