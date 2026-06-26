from __future__ import annotations

import json
from collections import Counter, defaultdict
from typing import Any

from velocity_claw.core.agent import VelocityClawAgent
from velocity_claw.core.failed_run_resume_install import install_failed_run_resume_class
from velocity_claw.memory.step_attempts_v2 import attempt_summary, effective_steps


install_failed_run_resume_class(VelocityClawAgent)


def _preview(content: Any, limit: int = 240) -> str:
    text = "" if content is None else str(content)
    return text[:limit]


def _artifact_json(artifact: dict[str, Any]) -> dict[str, Any]:
    try:
        payload = json.loads(artifact.get("content") or "{}")
    except (TypeError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def build_artifact_index(run: dict[str, Any]) -> dict[str, Any]:
    artifacts = run.get("artifacts", [])
    by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_step: dict[str, list[dict[str, Any]]] = defaultdict(list)
    counts = Counter()

    for index, artifact in enumerate(artifacts):
        artifact_type = artifact.get("artifact_type") or "text"
        step_id = artifact.get("step_id")
        key = "run_level" if step_id is None else f"step_{step_id}"
        item = {
            "index": index,
            "name": artifact.get("name"),
            "artifact_type": artifact_type,
            "step_id": step_id,
            "created_at": artifact.get("created_at"),
            "content_preview": _preview(artifact.get("content")),
            "content_size": len(str(artifact.get("content") or "")),
        }
        counts[artifact_type] += 1
        by_type[artifact_type].append(item)
        by_step[key].append(item)

    return {
        "total": len(artifacts),
        "counts_by_type": dict(counts),
        "by_type": dict(by_type),
        "by_step": dict(by_step),
    }


def build_step_index(run: dict[str, Any]) -> dict[str, Any]:
    records = run.get("steps", [])
    effective = effective_steps(records)
    status_counts = Counter(step.get("status") or "unknown" for step in effective)
    failed_steps = [step for step in effective if step.get("status") == "failed"]
    pending_approval_steps = [
        step for step in effective if step.get("status") == "pending_approval"
    ]
    history_by_step: dict[str, list[dict[str, Any]]] = defaultdict(list)

    attempt_records = []
    for step in records:
        item = {
            "record_id": step.get("record_id"),
            "id": step.get("id"),
            "title": step.get("title"),
            "tool": step.get("tool"),
            "status": step.get("status"),
            "attempt_no": step.get("attempt_no", 1),
            "phase": step.get("phase", "initial"),
            "started_at": step.get("started_at"),
            "completed_at": step.get("completed_at"),
            "has_error": bool(step.get("error")),
            "error": step.get("error"),
        }
        attempt_records.append(item)
        history_by_step[str(step.get("id"))].append(item)

    return {
        "total": len(effective),
        "total_attempt_records": len(records),
        "status_counts": dict(status_counts),
        "attempt_summary": attempt_summary(records),
        "failed_steps": [
            {
                "id": step.get("id"),
                "title": step.get("title"),
                "tool": step.get("tool"),
                "error": step.get("error"),
                "attempt_no": step.get("attempt_no", 1),
                "phase": step.get("phase", "initial"),
            }
            for step in failed_steps
        ],
        "pending_approval_steps": [
            {
                "id": step.get("id"),
                "title": step.get("title"),
                "tool": step.get("tool"),
                "attempt_no": step.get("attempt_no", 1),
                "phase": step.get("phase", "initial"),
                "approval_detail_url": f"/approvals/v2/{run.get('run_id')}/{step.get('id')}",
            }
            for step in pending_approval_steps
        ],
        "items": [
            {
                "record_id": step.get("record_id"),
                "id": step.get("id"),
                "title": step.get("title"),
                "tool": step.get("tool"),
                "status": step.get("status"),
                "attempt_no": step.get("attempt_no", 1),
                "phase": step.get("phase", "initial"),
                "started_at": step.get("started_at"),
                "completed_at": step.get("completed_at"),
                "has_error": bool(step.get("error")),
            }
            for step in effective
        ],
        "attempt_records": attempt_records,
        "history_by_step": dict(history_by_step),
    }


def build_resume_index(run: dict[str, Any]) -> dict[str, Any]:
    artifacts = run.get("artifacts", [])
    boundaries = [
        _artifact_json(item)
        for item in artifacts
        if item.get("artifact_type") == "resume_boundary"
    ]
    summaries = [
        _artifact_json(item)
        for item in artifacts
        if item.get("artifact_type") == "resume_summary"
    ]
    effective = effective_steps(run.get("steps", []))
    failed = next((step for step in effective if step.get("status") == "failed"), None)
    has_plan = any(item.get("name") == "run_plan" for item in artifacts)
    return {
        "resumable": bool(run.get("status") == "failed" and failed and has_plan),
        "resume_count": len(boundaries),
        "latest_boundary": boundaries[-1] if boundaries else None,
        "latest_summary": summaries[-1] if summaries else None,
        "boundaries": boundaries,
        "summaries": summaries,
        "failed_step_id": failed.get("id") if failed else None,
    }


def build_run_detail_v2(run: dict[str, Any]) -> dict[str, Any]:
    step_index = build_step_index(run)
    artifact_index = build_artifact_index(run)
    resume_index = build_resume_index(run)
    report = run.get("report") or {}
    forensics = run.get("forensics") or {}
    approval_history = run.get("approval_history") or []
    run_id = run.get("run_id")
    return {
        "run_id": run_id,
        "task": run.get("task"),
        "status": run.get("status"),
        "execution_profile": run.get("execution_profile", "unknown"),
        "created_at": run.get("created_at"),
        "completed_at": run.get("completed_at"),
        "summary": report.get("executive_summary"),
        "step_index": step_index,
        "artifact_index": artifact_index,
        "resume": resume_index,
        "approval_history": approval_history,
        "approval_events": len(approval_history),
        "forensic_highlights": {
            "failed_step": forensics.get("failed_step"),
            "pending_approval_step": forensics.get("pending_approval_step"),
            "last_step": forensics.get("last_step"),
            "artifact_counts_by_type": forensics.get("artifact_counts_by_type", {}),
            "step_attempts": forensics.get("step_attempts", {}),
        },
        "links": {
            "raw": f"/runs/{run_id}",
            "html": f"/runs/{run_id}/view",
            "report": f"/runs/{run_id}/report",
            "forensics": f"/runs/{run_id}/forensics",
            "artifacts_v2": f"/runs/{run_id}/artifacts/v2",
            "detail_v2": f"/runs/{run_id}/detail/v2",
            "resume_v2": f"/runs/{run_id}/resume/v2",
        },
    }
