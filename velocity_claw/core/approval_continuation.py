from __future__ import annotations

import json
from datetime import datetime
from typing import Any


def _now() -> str:
    return datetime.now().isoformat()


def _json_artifact(memory: Any, run_id: str, name: str, payload: dict[str, Any], *, step_id: int | None, artifact_type: str) -> None:
    memory.save_artifact(
        run_id,
        name,
        json.dumps(payload, ensure_ascii=False),
        step_id=step_id,
        artifact_type=artifact_type,
    )


def _next_event_number(run: dict[str, Any] | None, artifact_type: str) -> int:
    if not run:
        return 1
    return 1 + sum(1 for artifact in run.get("artifacts", []) if artifact.get("artifact_type") == artifact_type)


def _continuation_event(
    agent: Any,
    run_id: str,
    source_step_id: int,
    *,
    status: str,
    reason: str | None = None,
    start_index: int | None = None,
    boundary_step_id: int | None = None,
    failed_step_id: int | None = None,
    executed: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    executed = executed or []
    payload = {
        "status": status,
        "reason": reason,
        "source_step_id": source_step_id,
        "start_index": start_index,
        "boundary_step_id": boundary_step_id,
        "failed_step_id": failed_step_id,
        "executed_step_ids": [item.get("id") for item in executed],
        "executed_count": len(executed),
        "created_at": _now(),
    }
    run = agent.memory.load_run(run_id)
    event_no = _next_event_number(run, "approval_continuation")
    _json_artifact(
        agent.memory,
        run_id,
        f"approval_continuation_{event_no}_step_{source_step_id}",
        payload,
        step_id=source_step_id,
        artifact_type="approval_continuation",
    )
    return payload


def _pause_for_next_approval(
    agent: Any,
    run_id: str,
    task: str,
    step: dict[str, Any],
    profile_name: str,
    *,
    source_step_id: int,
) -> dict[str, Any]:
    step_id = step["id"]
    started_at = _now()
    completed_at = _now()
    approval = agent.approvals.build_record(step, profile_name=profile_name)
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
    agent.memory.save_step(run_id, step_result)
    _json_artifact(
        agent.memory,
        run_id,
        f"approval_step_{step_id}",
        approval,
        step_id=step_id,
        artifact_type="approval",
    )
    boundary = {
        "step_id": step_id,
        "source_step_id": source_step_id,
        "boundary_type": "continuation_pause",
        "created_at": completed_at,
    }
    _json_artifact(
        agent.memory,
        run_id,
        f"approval_boundary_step_{step_id}",
        boundary,
        step_id=step_id,
        artifact_type="approval_boundary",
    )
    agent.memory.save_approval_decision(
        run_id,
        step_id,
        "requested",
        actor=None,
        reason=approval.get("reason"),
        payload=approval,
    )
    agent.memory.save_project_note(
        "approval_pause",
        f"Run {run_id} paused during continuation from step {source_step_id} at step {step_id}",
    )
    agent.memory.update_run_status(run_id, "awaiting_approval")
    return {
        "run_id": run_id,
        "task": task,
        "status": "awaiting_approval",
        "summary": f"Run paused at continuation step {step_id} awaiting approval.",
        "step": step_result,
        "boundary": boundary,
    }


async def continue_after_approval(agent: Any, run_id: str, step_id: int) -> dict[str, Any]:
    run = agent.memory.load_run(run_id)
    if not run:
        return {
            "status": "failed",
            "reason": "run_not_found",
            "source_step_id": step_id,
            "executed": [],
        }

    artifacts = run.get("artifacts", [])
    plan_artifact = next((artifact for artifact in artifacts if artifact.get("name") == "run_plan"), None)
    if not plan_artifact:
        agent.memory.update_run_status(run_id, "approved_waiting_manual_resume")
        event = _continuation_event(
            agent,
            run_id,
            step_id,
            status="manual_resume_required",
            reason="run_plan_missing",
        )
        agent.memory.save_project_note("approval_manual_resume", f"Run {run_id} requires manual resume: run plan missing")
        return {**event, "executed": []}

    try:
        plan = json.loads(plan_artifact["content"])
    except (TypeError, ValueError, json.JSONDecodeError):
        agent.memory.update_run_status(run_id, "approved_waiting_manual_resume")
        event = _continuation_event(
            agent,
            run_id,
            step_id,
            status="manual_resume_required",
            reason="run_plan_invalid",
        )
        agent.memory.save_project_note("approval_manual_resume", f"Run {run_id} requires manual resume: run plan invalid")
        return {**event, "executed": []}

    steps = plan.get("steps") or []
    start_index = next((index for index, item in enumerate(steps) if item.get("id") == step_id), None)
    if start_index is None:
        agent.memory.update_run_status(run_id, "approved_waiting_manual_resume")
        event = _continuation_event(
            agent,
            run_id,
            step_id,
            status="manual_resume_required",
            reason="step_boundary_missing",
        )
        agent.memory.save_project_note("approval_manual_resume", f"Run {run_id} requires manual resume: step boundary missing")
        return {**event, "executed": []}

    executed: list[dict[str, Any]] = []
    profile_name = agent.settings.execution_profile
    for index, step in enumerate(steps[start_index:], start=start_index):
        if index > start_index and agent.approvals.requires_approval(step, profile_name):
            pause = _pause_for_next_approval(
                agent,
                run_id,
                run.get("task") or "",
                step,
                profile_name,
                source_step_id=step_id,
            )
            event = _continuation_event(
                agent,
                run_id,
                step_id,
                status="awaiting_approval",
                reason="next_approval_required",
                start_index=start_index,
                boundary_step_id=step.get("id"),
                executed=executed,
            )
            return {**event, "executed": executed, "pause": pause}

        started_at = _now()
        result = await agent.executor.execute_step(step, {})
        result["started_at"] = result.get("started_at") or started_at
        result["completed_at"] = _now()

        if index == start_index:
            agent.memory.update_step_status(
                run_id,
                step_id,
                result.get("status") or "failed",
                result=result.get("result"),
                error=result.get("error"),
            )
        else:
            agent.memory.save_step(run_id, result)

        if hasattr(agent, "_persist_artifacts"):
            agent._persist_artifacts(run_id, result)
        executed.append(result)

        if result.get("status") == "failed":
            agent.memory.update_run_status(run_id, "failed")
            agent.memory.save_project_note(
                "resume_failure",
                f"Run {run_id} failed during approval continuation at step {step.get('id')}",
            )
            event = _continuation_event(
                agent,
                run_id,
                step_id,
                status="failed",
                reason="step_execution_failed",
                start_index=start_index,
                failed_step_id=step.get("id"),
                executed=executed,
            )
            return {**event, "executed": executed}

    agent.memory.update_run_status(run_id, "completed")
    agent.memory.save_project_note("resume_complete", f"Run {run_id} completed after approval continuation")
    event = _continuation_event(
        agent,
        run_id,
        step_id,
        status="completed",
        reason="continuation_completed",
        start_index=start_index,
        executed=executed,
    )
    return {**event, "executed": executed}


async def approve_and_continue(agent: Any, run_id: str, step_id: int, *, actor: str, reason: str | None) -> dict[str, Any]:
    payload = {
        "decision": "approved",
        "actor": actor,
        "reason": reason,
        "decided_at": _now(),
    }
    agent.memory.update_step_status(run_id, step_id, "approved", result=payload)
    agent.memory.save_approval_decision(run_id, step_id, "approved", actor=actor, reason=reason, payload=payload)
    _json_artifact(
        agent.memory,
        run_id,
        f"approval_decision_step_{step_id}",
        payload,
        step_id=step_id,
        artifact_type="approval",
    )
    agent.memory.save_project_note("approval_decision", f"Run {run_id} step {step_id} approved by {actor}")
    agent.memory.update_run_status(run_id, "resuming_after_approval")
    payload["resume"] = await continue_after_approval(agent, run_id, step_id)
    return payload


def reject_with_boundary(agent: Any, run_id: str, step_id: int, *, actor: str, reason: str | None) -> dict[str, Any]:
    payload = {
        "decision": "rejected",
        "actor": actor,
        "reason": reason,
        "decided_at": _now(),
    }
    agent.memory.update_step_status(run_id, step_id, "rejected", result=payload, error="Rejected by reviewer")
    agent.memory.save_approval_decision(run_id, step_id, "rejected", actor=actor, reason=reason, payload=payload)
    _json_artifact(
        agent.memory,
        run_id,
        f"approval_decision_step_{step_id}",
        payload,
        step_id=step_id,
        artifact_type="approval",
    )
    rejection = {
        "status": "rejected",
        "run_id": run_id,
        "step_id": step_id,
        "actor": actor,
        "reason": reason,
        "continuation_allowed": False,
        "created_at": payload["decided_at"],
    }
    _json_artifact(
        agent.memory,
        run_id,
        f"approval_rejection_step_{step_id}",
        rejection,
        step_id=step_id,
        artifact_type="approval_rejection",
    )
    agent.memory.save_project_note("approval_decision", f"Run {run_id} step {step_id} rejected by {actor}")
    agent.memory.update_run_status(run_id, "rejected")
    payload["boundary"] = rejection
    return payload
