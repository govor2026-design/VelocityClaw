from __future__ import annotations

from dataclasses import dataclass
from typing import Any


TERMINAL_APPROVAL_STATUSES = {"approved", "rejected"}
PENDING_APPROVAL_STATUS = "pending_approval"


@dataclass(frozen=True)
class ApprovalDecisionGuard:
    allowed: bool
    reason: str
    current_status: str | None


def _find_step(run: dict[str, Any], step_id: int) -> dict[str, Any] | None:
    for step in run.get("steps", []):
        if step.get("id") == step_id:
            return step
    return None


def _step_artifacts(run: dict[str, Any], step_id: int) -> list[dict[str, Any]]:
    return [artifact for artifact in run.get("artifacts", []) if artifact.get("step_id") == step_id]


def _step_history(run: dict[str, Any], step_id: int) -> list[dict[str, Any]]:
    return [event for event in run.get("approval_history", []) if event.get("step_id") == step_id]


def evaluate_approval_decision(run: dict[str, Any] | None, step_id: int) -> ApprovalDecisionGuard:
    if not run:
        return ApprovalDecisionGuard(False, "run_not_found", None)
    step = _find_step(run, step_id)
    if not step:
        return ApprovalDecisionGuard(False, "step_not_found", None)
    status = step.get("status")
    if status != PENDING_APPROVAL_STATUS:
        if status in TERMINAL_APPROVAL_STATUSES:
            return ApprovalDecisionGuard(False, f"already_{status}", status)
        return ApprovalDecisionGuard(False, "step_not_pending_approval", status)
    return ApprovalDecisionGuard(True, "pending_approval", status)


def build_approval_detail(run: dict[str, Any] | None, step_id: int) -> dict[str, Any]:
    guard = evaluate_approval_decision(run, step_id)
    if not run:
        return {
            "status": "not_found",
            "reason": guard.reason,
            "run_id": None,
            "step_id": step_id,
            "can_decide": False,
        }

    step = _find_step(run, step_id)
    return {
        "status": "ok" if step else "not_found",
        "reason": guard.reason,
        "run_id": run.get("run_id"),
        "run_status": run.get("status"),
        "task": run.get("task"),
        "step_id": step_id,
        "step": step,
        "current_status": guard.current_status,
        "can_decide": guard.allowed,
        "history": _step_history(run, step_id),
        "artifacts": _step_artifacts(run, step_id),
        "links": {
            "approve": f"/approvals/v2/{run.get('run_id')}/{step_id}/approve",
            "reject": f"/approvals/v2/{run.get('run_id')}/{step_id}/reject",
            "run": f"/runs/{run.get('run_id')}",
            "run_view": f"/runs/{run.get('run_id')}/view",
        },
    }


async def approve_with_guard(agent: Any, run_id: str, step_id: int, actor: str, reason: str | None) -> dict[str, Any]:
    run = agent.memory.load_run(run_id)
    guard = evaluate_approval_decision(run, step_id)
    if not guard.allowed:
        return {
            "status": "blocked",
            "decision": "approve",
            "reason": guard.reason,
            "current_status": guard.current_status,
            "run_id": run_id,
            "step_id": step_id,
        }
    decision = await agent.approve_step(run_id, step_id, actor=actor, reason=reason)
    return {
        "status": "ok",
        "decision": decision,
        "approval": build_approval_detail(agent.memory.load_run(run_id), step_id),
    }


def reject_with_guard(agent: Any, run_id: str, step_id: int, actor: str, reason: str | None) -> dict[str, Any]:
    run = agent.memory.load_run(run_id)
    guard = evaluate_approval_decision(run, step_id)
    if not guard.allowed:
        return {
            "status": "blocked",
            "decision": "reject",
            "reason": guard.reason,
            "current_status": guard.current_status,
            "run_id": run_id,
            "step_id": step_id,
        }
    decision = agent.reject_step(run_id, step_id, actor=actor, reason=reason)
    return {
        "status": "ok",
        "decision": decision,
        "approval": build_approval_detail(agent.memory.load_run(run_id), step_id),
    }
