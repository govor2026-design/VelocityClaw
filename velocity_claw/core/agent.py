import asyncio
import json
from datetime import datetime
from typing import Dict, Optional
from velocity_claw.config.settings import Settings
from velocity_claw.logs.logger import get_logger
from velocity_claw.planner.planner import Planner
from velocity_claw.executor.executor import Executor
from velocity_claw.models.router import ModelRouter
from velocity_claw.memory.store import MemoryStore
from velocity_claw.security.policy import SecurityManager
from velocity_claw.security.access import ExecutionProfileManager, ApprovalManager
from velocity_claw.core.auto_fix import AutoFixLoop
from velocity_claw.core.modes import build_mode_task, HIGH_LEVEL_MODES


class VelocityClawAgent:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.logger = get_logger("velocity_claw.agent")
        self.router = ModelRouter(settings)
        self.planner = Planner(self.router, self.logger)
        self.executor = Executor(self.router, self.logger, settings)
        self.memory = MemoryStore(settings)
        self.security = SecurityManager(settings)
        self.profile_manager = ExecutionProfileManager(settings)
        self.approvals = ApprovalManager(settings)
        self.auto_fix = AutoFixLoop(self.executor.patch, self.executor.test_runner, self.executor.code_nav)

    def _get_profile_for_tool(self, tool: str) -> str:
        if tool in ["http.get", "http.post"]:
            return "network_allowlist"
        if tool in ["git.run"]:
            return "git_safe"
        if tool in ["fs.write", "fs.append", "fs.replace", "shell.run", "patch.apply", "test.run"]:
            return "workspace_write"
        return "read_only"

    async def run_mode(self, mode: str, task: str, context: Optional[Dict] = None) -> Dict:
        return await self.run_task(build_mode_task(mode, task), context)

    async def run_task(self, task: str, context: Optional[Dict] = None) -> Dict:
        run_id = self.memory.create_run(task)
        self.logger.info("Starting run %s for task: %s", run_id, task)
        self.memory.save_project_fact("last_task", task)
        try:
            self.logger.info("Run %s: Planning", run_id)
            plan = await self.planner.create_plan(task, context)
            self.memory.save_artifact(run_id, "run_plan", json.dumps(plan, ensure_ascii=False), artifact_type="plan")
            results = []
            for step in plan["steps"]:
                step_id = step["id"]
                self.logger.info("Run %s: Executing step %s", run_id, step_id)
                started_at = datetime.now().isoformat()
                profile_name = self.settings.execution_profile
                if self.approvals.requires_approval(step, profile_name):
                    completed_at = datetime.now().isoformat()
                    approval = self.approvals.build_record(step, f"Sensitive step for profile {profile_name}")
                    step_result = {
                        "id": step_id,
                        "title": step["title"],
                        "tool": step.get("tool"),
                        "args": step.get("args", {}),
                        "status": "pending_approval",
                        "result": approval,
                        "error": None,
                        "started_at": started_at,
                        "completed_at": completed_at,
                    }
                    results.append(step_result)
                    self.memory.save_step(run_id, step_result)
                    self.memory.save_artifact(run_id, f"approval_step_{step_id}", str(approval), step_id=step_id, artifact_type="approval")
                    self.memory.save_approval_decision(run_id, step_id, "requested", actor=None, reason=approval.get("reason"), payload=approval)
                    self.memory.update_run_status(run_id, "awaiting_approval")
                    return {
                        "run_id": run_id,
                        "task": task,
                        "status": "awaiting_approval",
                        "summary": f"Run paused at step {step_id} awaiting approval.",
                        "steps": results,
                        "signature": "velocity claw",
                    }

                if not self.profile_manager.is_tool_allowed(step.get("tool", ""), profile_name):
                    completed_at = datetime.now().isoformat()
                    step_result = {
                        "id": step_id,
                        "title": step["title"],
                        "tool": step.get("tool"),
                        "args": step.get("args", {}),
                        "status": "failed",
                        "result": None,
                        "error": f"Tool {step.get('tool')} is not allowed in profile {profile_name}",
                        "started_at": started_at,
                        "completed_at": completed_at,
                    }
                    results.append(step_result)
                    self.memory.save_step(run_id, step_result)
                    break

                profile = self.security.get_profile(self._get_profile_for_tool(step.get("tool", "")))
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
                self._persist_artifacts(run_id, step_result)
                if step_result["status"] == "failed":
                    break

            status = "completed" if results and all(r["status"] == "success" for r in results) else "failed"
            summary = self._build_summary(results)
            self.memory.update_run_status(run_id, status)
            self.memory.save_artifact(run_id, "run_summary", summary, artifact_type="summary")
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

    def run_auto_fix(self, *, target_test: str, patch_plan: list[dict], runner: str = "pytest", max_attempts: int = 2) -> dict:
        run_id = self.memory.create_run(f"auto_fix:{target_test}")
        result = self.auto_fix.run(target_test=target_test, patch_plan=patch_plan, runner=runner, max_attempts=max_attempts, dry_run=self.settings.dry_run)
        for attempt in result["attempts"]:
            self.memory.save_fix_attempt(run_id, attempt["attempt"], attempt)
            self.memory.save_artifact(run_id, f"auto_fix_attempt_{attempt['attempt']}", str(attempt), artifact_type="auto_fix")
        self.memory.update_run_status(run_id, "completed" if result["status"] == "completed" else "failed")
        result["run_id"] = run_id
        return result

    def resume_last_failed_run(self) -> Optional[Dict]:
        return self.memory.get_last_failed_run()

    def list_pending_approvals(self):
        return self.memory.list_pending_approvals()

    def get_approval_history(self, run_id: str):
        return self.memory.load_approval_history(run_id)

    def approve_step(self, run_id: str, step_id: int, actor: str = "owner", reason: str | None = None) -> dict:
        payload = {
            "decision": "approved",
            "actor": actor,
            "reason": reason,
            "decided_at": datetime.now().isoformat(),
        }
        self.memory.update_step_status(run_id, step_id, "approved", result=payload)
        self.memory.save_approval_decision(run_id, step_id, "approved", actor=actor, reason=reason, payload=payload)
        self.memory.save_artifact(run_id, f"approval_decision_step_{step_id}", str(payload), step_id=step_id, artifact_type="approval")
        resume = self.resume_after_approval(run_id, step_id)
        payload["resume"] = resume
        return payload

    def reject_step(self, run_id: str, step_id: int, actor: str = "owner", reason: str | None = None) -> dict:
        payload = {
            "decision": "rejected",
            "actor": actor,
            "reason": reason,
            "decided_at": datetime.now().isoformat(),
        }
        self.memory.update_step_status(run_id, step_id, "rejected", result=payload, error="Rejected by reviewer")
        self.memory.save_approval_decision(run_id, step_id, "rejected", actor=actor, reason=reason, payload=payload)
        self.memory.save_artifact(run_id, f"approval_decision_step_{step_id}", str(payload), step_id=step_id, artifact_type="approval")
        self.memory.update_run_status(run_id, "rejected")
        return payload

    def resume_after_approval(self, run_id: str, step_id: int) -> dict:
        run = self.memory.load_run(run_id)
        if not run:
            return {"status": "failed", "error": "run_not_found"}
        artifacts = run.get("artifacts", [])
        plan_artifact = next((a for a in artifacts if a.get("name") == "run_plan"), None)
        if not plan_artifact:
            self.memory.update_run_status(run_id, "approved_waiting_manual_resume")
            return {"status": "manual_resume_required", "reason": "run_plan_missing"}
        try:
            plan = json.loads(plan_artifact["content"])
        except Exception:
            self.memory.update_run_status(run_id, "approved_waiting_manual_resume")
            return {"status": "manual_resume_required", "reason": "run_plan_invalid"}
        pending_steps = [s for s in plan.get("steps", []) if s.get("id", 0) >= step_id]
        executed = []
        for step in pending_steps:
            result = asyncio.run(self.executor.execute_step(step, {}))
            result["started_at"] = result.get("started_at") or datetime.now().isoformat()
            result["completed_at"] = datetime.now().isoformat()
            self.memory.save_step(run_id, result)
            self._persist_artifacts(run_id, result)
            executed.append(result)
            if result.get("status") == "failed":
                self.memory.update_run_status(run_id, "failed")
                return {"status": "failed", "executed": executed}
        self.memory.update_run_status(run_id, "completed")
        return {"status": "completed", "executed": executed}

    def get_status(self) -> Dict:
        return {
            "status": "ready",
            "env": self.settings.env,
            "safe_mode": self.settings.safe_mode,
            "trusted_mode": self.settings.trusted_mode,
            "memory_enabled": self.settings.memory_enabled,
            "execution_profile": self.settings.execution_profile,
            "available_modes": sorted(HIGH_LEVEL_MODES.keys()),
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

    def _persist_artifacts(self, run_id: str, step_result: Dict) -> None:
        result = step_result.get("result")
        if not isinstance(result, dict):
            return
        step_id = step_result.get("id")
        if result.get("diff"):
            self.memory.save_artifact(run_id, f"step_{step_id}_diff", result["diff"], step_id=step_id, artifact_type="diff")
        if result.get("stdout"):
            self.memory.save_artifact(run_id, f"step_{step_id}_stdout", result["stdout"], step_id=step_id, artifact_type="log")
        if result.get("stderr"):
            self.memory.save_artifact(run_id, f"step_{step_id}_stderr", result["stderr"], step_id=step_id, artifact_type="log")
        if result.get("parsed_failures"):
            self.memory.save_artifact(run_id, f"step_{step_id}_failures", str(result["parsed_failures"]), step_id=step_id, artifact_type="failures")
