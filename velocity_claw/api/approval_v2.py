from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from typing import Any

from velocity_claw.core.approval_continuation import approve_and_continue, reject_with_boundary


TERMINAL_APPROVAL_STATUSES = {"approved", "rejected"}
PENDING_APPROVAL_STATUS = "pending_approval"
RISK_PRIORITY = {"high": 0, "medium": 1, "low": 2, "unknown": 3}


@dataclass(frozen=True)
class ApprovalDecisionGuard:
    allowed: bool
    reason: str
    current_status: str | None


def _find_step(run: dict[str, Any], step_id: int) -> dict[str, Any] | None:
    for step in reversed(run.get("steps", [])):
        if step.get("id") == step_id:
            return step
    return None


def _step_artifacts(run: dict[str, Any], step_id: int) -> list[dict[str, Any]]:
    return [artifact for artifact in run.get("artifacts", []) if artifact.get("step_id") == step_id]


def _step_history(run: dict[str, Any], step_id: int) -> list[dict[str, Any]]:
    return [event for event in run.get("approval_history", []) if event.get("step_id") == step_id]


def _latest_terminal_decision(run: dict[str, Any], step_id: int) -> str | None:
    for event in reversed(_step_history(run, step_id)):
        decision = event.get("decision")
        if decision in TERMINAL_APPROVAL_STATUSES:
            return decision
    return None


def _decode_artifact_content(artifact: dict[str, Any]) -> Any:
    content = artifact.get("content")
    if not isinstance(content, str):
        return content
    try:
        return json.loads(content)
    except (TypeError, ValueError, json.JSONDecodeError):
        return content


def _continuation_events(run: dict[str, Any], step_id: int) -> list[dict[str, Any]]:
    events = []
    for artifact in _step_artifacts(run, step_id):
        artifact_type = artifact.get("artifact_type")
        if artifact_type not in {"approval_continuation", "approval_rejection"}:
            continue
        events.append(
            {
                "name": artifact.get("name"),
                "artifact_type": artifact_type,
                "created_at": artifact.get("created_at"),
                "payload": _decode_artifact_content(artifact),
            }
        )
    return events


def _approval_record(pending: dict[str, Any], detail: dict[str, Any]) -> dict[str, Any]:
    pending_result = pending.get("result")
    if isinstance(pending_result, dict):
        return pending_result
    step = detail.get("step") or {}
    step_result = step.get("result")
    return step_result if isinstance(step_result, dict) else {}


def _normalize_risk(value: Any) -> str:
    normalized = str(value or "unknown").lower()
    return normalized if normalized in RISK_PRIORITY else "unknown"


def evaluate_approval_decision(run: dict[str, Any] | None, step_id: int) -> ApprovalDecisionGuard:
    if not run:
        return ApprovalDecisionGuard(False, "run_not_found", None)
    step = _find_step(run, step_id)
    if not step:
        return ApprovalDecisionGuard(False, "step_not_found", None)
    status = step.get("status")
    if status != PENDING_APPROVAL_STATUS:
        terminal_decision = _latest_terminal_decision(run, step_id)
        if terminal_decision:
            return ApprovalDecisionGuard(False, f"already_{terminal_decision}", status)
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
    continuation = _continuation_events(run, step_id)
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
        "continuation": continuation,
        "latest_continuation": continuation[-1] if continuation else None,
        "links": {
            "approve": f"/approvals/v2/{run.get('run_id')}/{step_id}/approve",
            "reject": f"/approvals/v2/{run.get('run_id')}/{step_id}/reject",
            "run": f"/runs/{run.get('run_id')}",
            "run_detail_v2": f"/runs/{run.get('run_id')}/detail/v2",
            "run_artifacts_v2": f"/runs/{run.get('run_id')}/artifacts/v2",
            "run_view": f"/runs/{run.get('run_id')}/view",
        },
    }


def build_approval_index(
    agent: Any,
    *,
    limit: int = 50,
    risk: str | None = None,
    tool: str | None = None,
) -> dict[str, Any]:
    pending = agent.list_pending_approvals()
    normalized_items: list[dict[str, Any]] = []

    for item in pending:
        run_id = item.get("run_id")
        step_id = item.get("step_id")
        run = agent.memory.load_run(run_id) if run_id else None
        detail = build_approval_detail(run, step_id) if isinstance(step_id, int) else {
            "status": "not_found",
            "can_decide": False,
            "history": [],
            "artifacts": [],
            "links": {},
        }
        record = _approval_record(item, detail)
        risk_level = _normalize_risk(record.get("risk_level"))
        reason = record.get("reason") or item.get("reason") or "Approval required."
        profile = record.get("profile")
        normalized_items.append(
            {
                "run_id": run_id,
                "run_status": detail.get("run_status"),
                "task": detail.get("task"),
                "step_id": step_id,
                "title": item.get("title") or (detail.get("step") or {}).get("title"),
                "tool": item.get("tool") or (detail.get("step") or {}).get("tool"),
                "args": item.get("args") or (detail.get("step") or {}).get("args") or {},
                "current_status": detail.get("current_status") or PENDING_APPROVAL_STATUS,
                "can_decide": detail.get("can_decide", False),
                "profile": profile,
                "risk_level": risk_level,
                "approval_label": record.get("approval_label"),
                "reason": reason,
                "triggers": record.get("triggers") or [],
                "operator_hint": record.get("operator_hint"),
                "next_step_hint": record.get("next_step_hint"),
                "recommended_action": record.get("recommended_action"),
                "summary": record.get("summary") or {},
                "history_count": len(detail.get("history") or []),
                "artifact_count": len(detail.get("artifacts") or []),
                "started_at": item.get("started_at"),
                "completed_at": item.get("completed_at"),
                "links": detail.get("links") or {},
            }
        )

    normalized_items.sort(
        key=lambda item: (
            RISK_PRIORITY.get(item.get("risk_level", "unknown"), RISK_PRIORITY["unknown"]),
            item.get("started_at") is None,
            item.get("started_at") or "",
            str(item.get("run_id") or ""),
            int(item.get("step_id") or 0),
        )
    )

    risk_filter = _normalize_risk(risk) if risk else None
    tool_filter = tool.strip() if tool else None
    matched = [
        item
        for item in normalized_items
        if (risk_filter is None or item.get("risk_level") == risk_filter)
        and (tool_filter is None or item.get("tool") == tool_filter)
    ]
    safe_limit = max(1, min(int(limit), 100))
    risk_counts = Counter(item.get("risk_level") or "unknown" for item in normalized_items)
    tool_counts = Counter(item.get("tool") or "unknown" for item in normalized_items)

    return {
        "status": "ok",
        "summary": {
            "total_pending": len(normalized_items),
            "matched": len(matched),
            "returned": min(len(matched), safe_limit),
            "counts_by_risk": dict(risk_counts),
            "counts_by_tool": dict(tool_counts),
            "decidable": sum(1 for item in normalized_items if item.get("can_decide")),
        },
        "filters": {
            "risk": risk_filter,
            "tool": tool_filter,
            "limit": safe_limit,
        },
        "items": matched[:safe_limit],
        "links": {
            "legacy": "/approvals",
            "dashboard_v2": "/dashboard/v2",
            "diagnostics_v2": "/diagnostics/v2",
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
    decision = await approve_and_continue(agent, run_id, step_id, actor=actor, reason=reason)
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
    decision = reject_with_boundary(agent, run_id, step_id, actor=actor, reason=reason)
    return {
        "status": "ok",
        "decision": decision,
        "approval": build_approval_detail(agent.memory.load_run(run_id), step_id),
    }
