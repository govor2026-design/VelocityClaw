from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

VALID_PROFILES = frozenset({"safe", "dev", "owner"})
VALID_RUN_STATUSES = frozenset(
    {"running", "completed", "failed", "cancelled", "paused", "pending_approval"}
)


def normalize_filter(value: Any) -> str | None:
    """Normalize optional dashboard query values.

    Empty strings and whitespace-only values are treated as no filter.
    """
    if value is None:
        return None
    normalized = str(value).strip().lower()
    return normalized or None


def run_profile(run: Mapping[str, Any] | None) -> str | None:
    """Return the execution profile from a run payload.

    Run data has evolved over time, so accept both top-level and nested
    metadata/config shapes used by persisted runs.
    """
    if not run:
        return None

    candidates = [
        run.get("profile"),
        run.get("execution_profile"),
    ]
    for container_name in ("metadata", "context", "settings", "config"):
        container = run.get(container_name)
        if isinstance(container, Mapping):
            candidates.extend((container.get("profile"), container.get("execution_profile")))

    for candidate in candidates:
        normalized = normalize_filter(candidate)
        if normalized:
            return normalized
    return None


def filter_runs(
    runs: Iterable[Mapping[str, Any]],
    *,
    status: str | None = None,
    profile: str | None = None,
) -> list[dict[str, Any]]:
    """Filter runs by normalized status and execution profile."""
    status_filter = normalize_filter(status)
    profile_filter = normalize_filter(profile)

    filtered: list[dict[str, Any]] = []
    for run in runs:
        if not isinstance(run, Mapping):
            continue
        run_status = normalize_filter(run.get("status"))
        if status_filter and run_status != status_filter:
            continue
        if profile_filter and run_profile(run) != profile_filter:
            continue
        filtered.append(dict(run))
    return filtered


def _result_preview(value: Any, *, limit: int = 500) -> str:
    if value is None:
        return ""
    text = str(value)
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1]}…"


def compact_step_inspector(run: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Build a compact, display-safe run and step summary for the dashboard."""
    if not run:
        return None

    raw_steps = run.get("steps")
    if not isinstance(raw_steps, list):
        plan = run.get("plan")
        raw_steps = plan.get("steps", []) if isinstance(plan, Mapping) else []

    steps: list[dict[str, Any]] = []
    for index, raw_step in enumerate(raw_steps, start=1):
        if not isinstance(raw_step, Mapping):
            continue
        result = raw_step.get("result")
        if isinstance(result, Mapping):
            result = result.get("summary") or result.get("output") or result
        error = raw_step.get("error")
        if isinstance(error, Mapping):
            error = error.get("detail") or error.get("message") or error
        steps.append(
            {
                "id": raw_step.get("id", raw_step.get("step_id", index)),
                "title": raw_step.get("title") or raw_step.get("description") or raw_step.get("task") or "",
                "tool": raw_step.get("tool") or raw_step.get("action") or "",
                "status": raw_step.get("status") or "unknown",
                "error": _result_preview(error),
                "result_preview": _result_preview(result),
            }
        )

    artifacts = run.get("artifacts")
    artifact_count = len(artifacts) if isinstance(artifacts, (list, tuple, dict, set)) else 0

    return {
        "run_id": run.get("run_id") or run.get("id") or "",
        "task": run.get("task") or run.get("title") or "",
        "status": run.get("status") or "unknown",
        "profile": run_profile(run),
        "step_count": len(steps),
        "artifact_count": artifact_count,
        "steps": steps,
    }
