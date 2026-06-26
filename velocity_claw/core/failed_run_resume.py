from __future__ import annotations

import asyncio
import json
from datetime import datetime
from types import MethodType
from typing import Any

from velocity_claw.memory.step_attempts_v2 import effective_steps


class FailedRunResumeError(RuntimeError):
    def __init__(self, code: str, detail: str, *, status_code: int = 409):
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.status_code = status_code


class FailedRunResumer:
    def __init__(self, agent: Any):
        self.agent = agent
        self._locks: dict[str, asyncio.Lock] = {}

    def _lock_for(self, run_id: str) -> asyncio.Lock:
        lock = self._locks.get(run_id)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[run_id] = lock
        return lock

    def _artifact_json(self, run: dict[str, Any], name: str, default: Any = None) -> Any:
        artifact = next(
            (item for item in reversed(run.get("artifacts") or []) if item.get("name") == name),
            None,
        )
        if not artifact:
            return default
        try:
            return json.loads(artifact.get("content") or "null")
        except (TypeError, ValueError):
            return default

    def _plan(self, run: dict[str, Any]) -> dict[str, Any]:
        plan = self._artifact_json(run, "run_plan")
        if not isinstance(plan, dict) or not isinstance(plan.get("steps"), list):
            raise FailedRunResumeError(
                "run_plan_missing",
                "Run does not contain a valid persisted plan.",
            )
        return plan

    def _failed_step_index(
        self,
        plan_steps: list[dict[str, Any]],
        step_records: list[dict[str, Any]],
    ) -> int:
        latest_by_id = {
            step.get("id"): step
            for step in effective_steps(step_records)
            if step.get("id") is not None
        }
        for index, planned in enumerate(plan_steps):
            record = latest_by_id.get(planned.get("id"))
            if record and record.get("status") == "failed":
                return index
        raise FailedRunResumeError(
            "failed_step_not_found",
            "Run is marked failed but has no effective failed step to resume.",
        )

    def _resume_number(self, run: dict[str, Any]) -> int:
        count = sum(
            1
            for artifact in run.get("artifacts") or []
            if artifact.get("artifact_type") == "resume_boundary"
        )
        return count + 1

    def _attempt_for_step(self, records: list[dict[str, Any]], step_id: Any) -> int:
        attempts = [
            int(item.get("attempt_no") or 1)
            for item in records
            if item.get("id") == step_id
        ]
        return max(attempts, default=0) + 1

    def preview(self, run_id: str) -> dict[str, Any]:
        run = self.agent.memory.load_run(run_id)
        if not run:
            raise FailedRunResumeError("run_not_found", "Run not found.", status_code=404)
        if run.get("status") != "failed":
            raise FailedRunResumeError(
                "run_not_failed",
                f"Only failed runs can be resumed; current status is {run.get('status')}.",
            )

        plan = self._plan(run)
        plan_steps = plan.get("steps") or []
        failed_index = self._failed_step_index(plan_steps, run.get("steps") or [])
        failed_step = plan_steps[failed_index]
        lock = self._locks.get(run_id)
        profile = self.agent._profile_for_run(run)
        return {
            "run_id": run_id,
            "status": run.get("status"),
            "resumable": True,
            "resume_in_progress": bool(lock and lock.locked()),
            "execution_profile": profile,
            "from_step_id": failed_step.get("id"),
            "from_step_index": failed_index,
            "remaining_step_ids": [item.get("id") for item in plan_steps[failed_index:]],
            "skipped_completed_step_ids": [item.get("id") for item in plan_steps[:failed_index]],
            "next_resume_number": self._resume_number(run),
            "next_attempt_no": self._attempt_for_step(
                run.get("steps") or [],
                failed_step.get("id"),
            ),
            "links": {
                "run_detail_v2": f"/runs/{run_id}/detail/v2",
                "artifacts_v2": f"/runs/{run_id}/artifacts/v2",
                "resume_v2": f"/runs/{run_id}/resume/v2",
            },
        }

    def _execution_context(self, run: dict[str, Any]) -> dict[str, Any]:
        context = self._artifact_json(run, "planning_context", default={})
        return context if isinstance(context, dict) else {}

    def _save_boundary(
        self,
        run: dict[str, Any],
        preview: dict[str, Any],
        *,
        actor: str,
        reason: str | None,
    ) -> dict[str, Any]:
        boundary = {
            "run_id": run["run_id"],
            "resume_number": preview["next_resume_number"],
            "from_step_id": preview["from_step_id"],
            "remaining_step_ids": preview["remaining_step_ids"],
            "skipped_completed_step_ids": preview["skipped_completed_step_ids"],
            "execution_profile": preview["execution_profile"],
            "actor": actor,
            "reason": reason,
            "started_at": datetime.now().isoformat(),
        }
        self.agent.memory.save_artifact(
            run["run_id"],
            f"failed_resume_boundary_{boundary['resume_number']}",
            json.dumps(boundary, ensure_ascii=False),
            step_id=preview["from_step_id"],
            artifact_type="resume_boundary",
        )
        self.agent.memory.save_project_note(
            "failed_resume",
            f"Run {run['run_id']} resumed from step {preview['from_step_id']} (resume {boundary['resume_number']})",
        )
        return boundary

    def _save_summary(
        self,
        run_id: str,
        boundary: dict[str, Any],
        *,
        status: str,
        executed: list[dict[str, Any]],
        boundary_step_id: Any = None,
    ) -> dict[str, Any]:
        summary = {
            "run_id": run_id,
            "resume_number": boundary["resume_number"],
            "from_step_id": boundary["from_step_id"],
            "status": status,
            "executed_step_ids": [item.get("id") for item in executed],
            "boundary_step_id": boundary_step_id,
            "completed_at": datetime.now().isoformat(),
        }
        self.agent.memory.save_artifact(
            run_id,
            f"failed_resume_summary_{boundary['resume_number']}",
            json.dumps(summary, ensure_ascii=False),
            step_id=boundary_step_id or boundary["from_step_id"],
            artifact_type="resume_summary",
        )
        return summary

    def _pause_for_resume_approval(
        self,
        *,
        run: dict[str, Any],
        step: dict[str, Any],
        profile_name: str,
        attempt_no: int,
        resume_number: int,
        executed: list[dict[str, Any]],
    ) -> dict[str, Any]:
        started_at = datetime.now().isoformat()
        approval = self.agent.approvals.build_record(step, profile_name=profile_name)
        step_result = {
            "id": step.get("id"),
            "title": step.get("title"),
            "tool": step.get("tool"),
            "args": step.get("args", {}),
            "status": "pending_approval",
            "result": approval,
            "error": None,
            "started_at": started_at,
            "completed_at": datetime.now().isoformat(),
            "attempt_no": attempt_no,
            "phase": "failed_resume",
        }
        self.agent.memory.save_step(
            run["run_id"],
            step_result,
            attempt_no=attempt_no,
            phase="failed_resume",
        )
        payload = {
            "step_id": step.get("id"),
            "boundary_type": "failed_resume_approval",
            "resume_number": resume_number,
            "attempt_no": attempt_no,
            "phase": "failed_resume",
        }
        self.agent.memory.save_artifact(
            run["run_id"],
            f"approval_step_{step.get('id')}_resume_{resume_number}",
            json.dumps(approval, ensure_ascii=False),
            step_id=step.get("id"),
            artifact_type="approval",
        )
        self.agent.memory.save_artifact(
            run["run_id"],
            f"approval_boundary_step_{step.get('id')}_resume_{resume_number}",
            json.dumps(payload, ensure_ascii=False),
            step_id=step.get("id"),
            artifact_type="approval_boundary",
        )
        self.agent.memory.save_approval_decision(
            run["run_id"],
            step.get("id"),
            "requested",
            actor=None,
            reason=approval.get("reason"),
            payload={**approval, **payload},
        )
        self.agent.memory.update_run_status(run["run_id"], "awaiting_approval")
        return {
            "status": "awaiting_approval",
            "run_id": run["run_id"],
            "boundary_step_id": step.get("id"),
            "executed": executed,
            "approval": approval,
            "resume_number": resume_number,
        }

    async def _execute_from(
        self,
        *,
        run: dict[str, Any],
        plan_steps: list[dict[str, Any]],
        start_index: int,
        profile_name: str,
        boundary: dict[str, Any],
        approved_step_id: Any = None,
    ) -> dict[str, Any]:
        records = list(run.get("steps") or [])
        context = self._execution_context(run)
        executed: list[dict[str, Any]] = []

        for step in plan_steps[start_index:]:
            step_id = step.get("id")
            attempt_no = self._attempt_for_step(records, step_id)
            approved = approved_step_id is not None and step_id == approved_step_id
            outcome = await self.agent.step_guard.execute(
                step,
                context,
                profile_name,
                approved=approved,
                started_at=datetime.now().isoformat(),
            )
            if outcome["state"] == "approval_required":
                paused = self._pause_for_resume_approval(
                    run=run,
                    step=step,
                    profile_name=profile_name,
                    attempt_no=attempt_no,
                    resume_number=boundary["resume_number"],
                    executed=executed,
                )
                paused["resume_summary"] = self._save_summary(
                    run["run_id"],
                    boundary,
                    status="awaiting_approval",
                    executed=executed,
                    boundary_step_id=step_id,
                )
                return paused

            step_result = outcome["step_result"]
            step_result["attempt_no"] = attempt_no
            step_result["phase"] = "failed_resume"
            self.agent.memory.save_step(
                run["run_id"],
                step_result,
                attempt_no=attempt_no,
                phase="failed_resume",
            )
            self.agent._persist_artifacts(run["run_id"], step_result)
            executed.append(step_result)
            records.append(step_result)

            if step_result.get("status") == "failed":
                self.agent.memory.update_run_status(run["run_id"], "failed")
                summary = self._save_summary(
                    run["run_id"],
                    boundary,
                    status="failed",
                    executed=executed,
                )
                self.agent.memory.save_project_note(
                    "failed_resume_failure",
                    f"Run {run['run_id']} failed during resume {boundary['resume_number']} at step {step_id}",
                )
                return {
                    "status": "failed",
                    "run_id": run["run_id"],
                    "resume_number": boundary["resume_number"],
                    "executed": executed,
                    "resume_summary": summary,
                }

        self.agent.memory.update_run_status(run["run_id"], "completed")
        summary = self._save_summary(
            run["run_id"],
            boundary,
            status="completed",
            executed=executed,
        )
        self.agent.memory.save_project_note(
            "failed_resume_complete",
            f"Run {run['run_id']} completed during resume {boundary['resume_number']}",
        )
        return {
            "status": "completed",
            "run_id": run["run_id"],
            "resume_number": boundary["resume_number"],
            "executed": executed,
            "resume_summary": summary,
        }

    async def resume(
        self,
        run_id: str,
        *,
        actor: str = "operator",
        reason: str | None = None,
    ) -> dict[str, Any]:
        lock = self._lock_for(run_id)
        if lock.locked():
            raise FailedRunResumeError(
                "resume_in_progress",
                "A failed-run resume is already in progress for this run.",
            )

        async with lock:
            run = self.agent.memory.load_run(run_id)
            preview = self.preview(run_id)
            plan = self._plan(run)
            boundary = self._save_boundary(run, preview, actor=actor, reason=reason)
            self.agent.memory.update_run_status(run_id, "resuming_failed_run")
            return await self._execute_from(
                run=run,
                plan_steps=plan["steps"],
                start_index=preview["from_step_index"],
                profile_name=preview["execution_profile"],
                boundary=boundary,
            )

    async def continue_after_approval(
        self,
        run_id: str,
        step_id: int,
    ) -> dict[str, Any]:
        lock = self._lock_for(run_id)
        if lock.locked():
            raise FailedRunResumeError(
                "resume_in_progress",
                "A failed-run resume is already in progress for this run.",
            )

        async with lock:
            run = self.agent.memory.load_run(run_id)
            if not run:
                raise FailedRunResumeError("run_not_found", "Run not found.", status_code=404)
            plan = self._plan(run)
            start_index = next(
                (index for index, item in enumerate(plan["steps"]) if item.get("id") == step_id),
                None,
            )
            if start_index is None:
                raise FailedRunResumeError(
                    "step_boundary_missing",
                    "Approved step is not present in the persisted run plan.",
                )
            boundary_artifacts = [
                item
                for item in run.get("artifacts") or []
                if item.get("artifact_type") == "resume_boundary"
            ]
            if not boundary_artifacts:
                raise FailedRunResumeError(
                    "resume_boundary_missing",
                    "Failed-run resume boundary is missing.",
                )
            try:
                boundary = json.loads(boundary_artifacts[-1].get("content") or "{}")
            except (TypeError, ValueError):
                boundary = {}
            if not boundary.get("resume_number"):
                raise FailedRunResumeError(
                    "resume_boundary_invalid",
                    "Failed-run resume boundary is invalid.",
                )
            self.agent.memory.update_run_status(run_id, "resuming_failed_run")
            return await self._execute_from(
                run=run,
                plan_steps=plan["steps"],
                start_index=start_index,
                profile_name=self.agent._profile_for_run(run),
                boundary=boundary,
                approved_step_id=step_id,
            )


def install_failed_run_resume_instance(agent: Any) -> FailedRunResumer:
    existing = getattr(agent, "failed_run_resumer", None)
    if existing is not None:
        return existing

    resumer = FailedRunResumer(agent)
    original_resume_after_approval = agent.resume_after_approval

    def get_failed_run_resume_state(self, run_id: str):
        return self.failed_run_resumer.preview(run_id)

    async def resume_failed_run(self, run_id: str, actor: str = "operator", reason: str | None = None):
        return await self.failed_run_resumer.resume(run_id, actor=actor, reason=reason)

    async def resume_after_approval(self, run_id: str, step_id: int):
        run = self.memory.load_run(run_id)
        latest = next(
            (
                item
                for item in reversed((run or {}).get("steps") or [])
                if item.get("id") == step_id
            ),
            None,
        )
        if latest and latest.get("phase") == "failed_resume":
            return await self.failed_run_resumer.continue_after_approval(run_id, step_id)
        return await original_resume_after_approval(run_id, step_id)

    agent.failed_run_resumer = resumer
    agent.get_failed_run_resume_state = MethodType(get_failed_run_resume_state, agent)
    agent.resume_failed_run = MethodType(resume_failed_run, agent)
    agent.resume_after_approval = MethodType(resume_after_approval, agent)
    return resumer
