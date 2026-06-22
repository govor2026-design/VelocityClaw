from __future__ import annotations

from typing import Any


VALID_RUN_STATUSES = {"running", "completed", "failed", "cancelled", "paused", "pending_approval"}
VALID_PROFILES = {"safe", "dev", "owner"}


def normalize_filter(value: str | None) -> str | None:
    normalized = (value or "").strip().lower()
    return normalized or None


def run_profile(run: dict[str, Any]) -> str | None:
    direct = run.get("execution_profile") or run.get("profile")
    if direct:
        return str(direct).strip().lower()
    context = run.get("context") if isinstance(run.get("context"), dict) else {}
    nested = context.get("execution_profile") or context.get("profile")
    return str(nested).strip().lower() if nested else None


def filter_runs(runs: list[dict[str, Any]], *, status: str | None = None, profile: str | None = None) -> list[dict[str, Any]]:
    status_filter = normalize_filter(status)
    profile_filter = normalize_filter(profile)
    filtered = []
    for run in runs:
        current_status = str(run.get("status") or "unknown").strip().lower()
        current_profile = run_profile(run)
        if status_filter and current_status != status_filter:
            continue
        if profile_filter and current_profile != profile_filter:
            continue
        filtered.append(run)
    return filtered


def compact_step_inspector(run: dict[str, Any] | None, limit: int = 25) -> dict[str, Any] | None:
    if not run:
        return None
    steps = []
    for step in (run.get("steps") or [])[: max(1, min(limit, 100))]:
        result = step.get("result")
        result_preview = ""
        if result is not None:
            result_preview = str(result)
            if len(result_preview) > 240:
                result_preview = result_preview[:237] + "..."
        steps.append({"id": step.get("id"), "title": step.get("title"), "tool": step.get("tool"), "status": step.get("status"), "error": step.get("error"), "result_preview": result_preview})
    return {"run_id": run.get("run_id"), "task": run.get("task"), "status": run.get("status"), "profile": run_profile(run), "step_count": len(run.get("steps") or []), "artifact_count": len(run.get("artifacts") or []), "steps": steps}
