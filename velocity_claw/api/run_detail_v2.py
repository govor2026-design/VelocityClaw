from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any


def _preview(content: Any, limit: int = 240) -> str:
    text = "" if content is None else str(content)
    return text[:limit]


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
    steps = run.get("steps", [])
    status_counts = Counter(step.get("status") or "unknown" for step in steps)
    failed_steps = [step for step in steps if step.get("status") == "failed"]
    pending_approval_steps = [step for step in steps if step.get("status") == "pending_approval"]
    return {
        "total": len(steps),
        "status_counts": dict(status_counts),
        "failed_steps": [
            {
                "id": step.get("id"),
                "title": step.get("title"),
                "tool": step.get("tool"),
                "error": step.get("error"),
            }
            for step in failed_steps
        ],
        "pending_approval_steps": [
            {
                "id": step.get("id"),
                "title": step.get("title"),
                "tool": step.get("tool"),
                "approval_detail_url": f"/approvals/v2/{run.get('run_id')}/{step.get('id')}",
            }
            for step in pending_approval_steps
        ],
        "items": [
            {
                "id": step.get("id"),
                "title": step.get("title"),
                "tool": step.get("tool"),
                "status": step.get("status"),
                "started_at": step.get("started_at"),
                "completed_at": step.get("completed_at"),
                "has_error": bool(step.get("error")),
            }
            for step in steps
        ],
    }


def build_run_detail_v2(run: dict[str, Any]) -> dict[str, Any]:
    step_index = build_step_index(run)
    artifact_index = build_artifact_index(run)
    report = run.get("report") or {}
    forensics = run.get("forensics") or {}
    approval_history = run.get("approval_history") or []
    return {
        "run_id": run.get("run_id"),
        "task": run.get("task"),
        "status": run.get("status"),
        "created_at": run.get("created_at"),
        "completed_at": run.get("completed_at"),
        "summary": report.get("executive_summary"),
        "step_index": step_index,
        "artifact_index": artifact_index,
        "approval_history": approval_history,
        "approval_events": len(approval_history),
        "forensic_highlights": {
            "failed_step": forensics.get("failed_step"),
            "pending_approval_step": forensics.get("pending_approval_step"),
            "last_step": forensics.get("last_step"),
            "artifact_counts_by_type": forensics.get("artifact_counts_by_type", {}),
        },
        "links": {
            "raw": f"/runs/{run.get('run_id')}",
            "html": f"/runs/{run.get('run_id')}/view",
            "report": f"/runs/{run.get('run_id')}/report",
            "forensics": f"/runs/{run.get('run_id')}/forensics",
            "artifacts_v2": f"/runs/{run.get('run_id')}/artifacts/v2",
            "detail_v2": f"/runs/{run.get('run_id')}/detail/v2",
        },
    }
