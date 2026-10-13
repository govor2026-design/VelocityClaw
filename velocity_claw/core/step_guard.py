from __future__ import annotations

import asyncio
from typing import Any, Callable

from velocity_claw.timestamps import utc_now_iso
from velocity_claw.failures import FailureType, classify_failure


class StepExecutionGuard:
    RETRY_SAFE_TOOLS = {
        "analysis",
        "code.find_references",
        "code.find_routes",
        "code.find_symbol",
        "code.list_imports",
        "code.read_lines",
        "code.read_symbol",
        "fs.read",
        "git.inspect",
        "http.get",
        "patch.preview",
        "test.run",
    }

    def __init__(
        self,
        *,
        profile_manager: Any,
        security: Any,
        executor: Any,
        profile_selector: Callable[[str], str],
        logger: Any,
        max_retries: int = 0,
        retry_backoff_ms: int = 0,
        sleep: Callable[[float], Any] = asyncio.sleep,
    ):
        self.profile_manager = profile_manager
        self.security = security
        self.executor = executor
        self.profile_selector = profile_selector
        self.logger = logger
        self.max_retries = max(0, int(max_retries))
        self.retry_backoff_ms = max(0, int(retry_backoff_ms))
        self.sleep = sleep

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

    def _failed_result(
        self,
        step: dict,
        started_at: str,
        error: str,
        policy: dict,
        error_type: str,
    ) -> dict:
        return {
            "id": step.get("id"),
            "title": step.get("title", "unknown"),
            "tool": step.get("tool"),
            "args": step.get("args", {}),
            "status": "failed",
            "result": {"policy": policy},
            "error": error,
            "error_type": error_type,
            "started_at": started_at,
            "completed_at": utc_now_iso(),
        }

    async def execute(
        self,
        step: dict,
        context: dict,
        profile_name: str,
        *,
        approved: bool = False,
        started_at: str | None = None,
        attempt_no: int = 1,
        phase: str = "initial",
    ) -> dict:
        started_at = started_at or utc_now_iso()
        policy = self.evaluate(step, profile_name, approved=approved)

        if policy["blocked"]:
            failure = self._failed_result(
                step,
                started_at,
                policy["reason"],
                policy,
                FailureType.POLICY_DENIED.value,
            )
            failure.update(
                attempt_no=max(1, int(attempt_no)),
                phase=phase,
                retry_count=0,
                retryable=False,
            )
            return {
                "state": "blocked",
                "policy": policy,
                "step_result": failure,
                "attempts": [failure],
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
            failure = self._failed_result(
                step,
                started_at,
                str(exc),
                policy,
                classify_failure(exc, phase="security", tool=step.get("tool")),
            )
            failure.update(
                attempt_no=max(1, int(attempt_no)),
                phase=phase,
                retry_count=0,
                retryable=False,
            )
            return {
                "state": "security_failed",
                "policy": policy,
                "step_result": failure,
                "attempts": [failure],
            }

        attempts = []
        first_attempt = max(1, int(attempt_no))
        for retry_count in range(self.max_retries + 1):
            result = await self.executor.execute_step(step, context)
            result.setdefault("error_type", None)
            result.setdefault("retryable", False)
            result["started_at"] = result.get("started_at") or (
                started_at if retry_count == 0 else utc_now_iso()
            )
            result["completed_at"] = utc_now_iso()
            result["attempt_no"] = first_attempt + retry_count
            result["phase"] = phase
            result["retry_count"] = retry_count
            result["policy"] = {
                "profile": policy["profile"],
                "mode": policy["mode"],
                "approved": policy["approved"],
            }
            attempts.append(result)
            if result.get("status") != "failed":
                break
            if not self._should_retry(step, result) or retry_count >= self.max_retries:
                break
            delay = (self.retry_backoff_ms / 1000.0) * (retry_count + 1)
            self.logger.warning(
                "Retrying step %s after transient %s failure (%s/%s)",
                step.get("id"),
                result.get("error_type"),
                retry_count + 1,
                self.max_retries,
            )
            if delay:
                await self.sleep(delay)

        return {
            "state": "executed",
            "policy": policy,
            "step_result": attempts[-1],
            "attempts": attempts,
        }

    def _should_retry(self, step: dict, result: dict) -> bool:
        return bool(
            result.get("retryable")
            and step.get("tool") in self.RETRY_SAFE_TOOLS
        )
