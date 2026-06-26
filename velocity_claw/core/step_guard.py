from __future__ import annotations

from datetime import datetime
from typing import Any, Callable


class StepExecutionGuard:
    def __init__(
        self,
        *,
        profile_manager: Any,
        security: Any,
        executor: Any,
        profile_selector: Callable[[str], str],
        logger: Any,
    ):
        self.profile_manager = profile_manager
        self.security = security
        self.executor = executor
        self.profile_selector = profile_selector
        self.logger = logger

    def evaluate(self, step: dict, profile_name: str, *, approved: bool = False) -> dict:
        args = step.get("args", {}) or {}
        return self.profile_manager.evaluate_tool(
            step.get("tool", ""),
            profile_name,
            approved=approved,
            explicit_approval=args.get("require_approval") is True,
        )

    def _validate_security(self, step: dict) -> None:
        tool = step.get("tool", "")
        args = step.get("args", {}) or {}
        access_profile = self.security.get_profile(self.profile_selector(tool))
        if tool == "shell.run":
            self.security.validate_command(args.get("command", ""), access_profile)
        elif tool == "fs.read":
            self.security.validate_path(args.get("path", ""), access_profile, write=False)
        elif tool in {"fs.write", "fs.append", "fs.replace"}:
            self.security.validate_path(args.get("path", ""), access_profile, write=True)
        elif tool in {"http.get", "http.post"}:
            self.security.validate_url(args.get("url", ""), access_profile)
        elif tool == "git.run":
            self.security.validate_git_command(args.get("command", ""), access_profile)

    def _failed_result(self, step: dict, started_at: str, error: str, policy: dict) -> dict:
        return {
            "id": step.get("id"),
            "title": step.get("title", "unknown"),
            "tool": step.get("tool"),
            "args": step.get("args", {}),
            "status": "failed",
            "result": {"policy": policy},
            "error": error,
            "started_at": started_at,
            "completed_at": datetime.now().isoformat(),
        }

    async def execute(
        self,
        step: dict,
        context: dict,
        profile_name: str,
        *,
        approved: bool = False,
        started_at: str | None = None,
    ) -> dict:
        started_at = started_at or datetime.now().isoformat()
        policy = self.evaluate(step, profile_name, approved=approved)

        if policy["blocked"]:
            return {
                "state": "blocked",
                "policy": policy,
                "step_result": self._failed_result(step, started_at, policy["reason"], policy),
            }
        if policy["requires_approval"]:
            return {
                "state": "approval_required",
                "policy": policy,
                "step_result": None,
            }

        try:
            self._validate_security(step)
        except Exception as exc:
            self.logger.error(
                "Security validation failed for step %s under profile %s: %s",
                step.get("id"),
                profile_name,
                exc,
            )
            return {
                "state": "security_failed",
                "policy": policy,
                "step_result": self._failed_result(step, started_at, str(exc), policy),
            }

        result = await self.executor.execute_step(step, context)
        result["started_at"] = result.get("started_at") or started_at
        result["completed_at"] = datetime.now().isoformat()
        result["policy"] = {
            "profile": policy["profile"],
            "mode": policy["mode"],
            "approved": policy["approved"],
        }
        return {
            "state": "executed",
            "policy": policy,
            "step_result": result,
        }
