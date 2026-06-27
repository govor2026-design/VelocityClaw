from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

VALID_PROFILES = frozenset({"safe", "dev", "owner"})
VALID_RUN_STATUSES = frozenset(
    {
        "queued",
        "running",
        "completed",
        "failed",
        "cancelled",
        "paused",
        "pending_approval",
        "awaiting_approval",
    }
)


def normalize_filter(value: str | None, valid_values: Iterable[str]) -> str | None:
    """Normalize a dashboard query filter and reject unsupported values."""
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if not normalized:
        return None
    allowed = set(valid_values)
    return normalized if normalized in allowed else None


def run_profile(run: Mapping[str, Any] | None) -> str | None:
    """Return a normalized execution profile from a run payload."""
    if not run:
        return None

    direct = run.get("execution_profile") or run.get("profile")
    if direct is None:
        context = run.get("context")
        if isinstance(context, Mapping):
            direct = context.get("execution_profile") or context.get("profile")
    if direct is None:
        metadata = run.get("metadata")
        if isinstance(metadata, Mapping):
            direct = metadata.get("execution_profile") or metadata.get("profile")
    return normalize_filter(str(direct) if direct is not None else None, VALID_PROFILES)


def filter_runs(
    runs: Iterable[Mapping[str, Any]],
    *,
    status: str | None = None,
    profile: str | None = None,
) -> list[dict[str, Any]]:
    """Filter run records by supported status and profile values."""
    normalized_status = normalize_filter(status, VALID_RUN_STATUSES)
    normalized_profile = normalize_filter(profile, VALID_PROFILES)
    filtered: list[dict[str, Any]] = []
    for item in runs:
        run = dict(item)
        run_status = str(run.get("status") or "").strip().lower()
        if normalized_status and run_status != normalized_status:
            continue
        if normalized_profile and run_profile(run) != normalized_profile:
            continue
        filtered.append(run)
    return filtered


def _preview(value: Any, *, limit: int = 240) -> str:
    if value is None:
        return ""
    text = str(value)
    return text if len(text) <= limit else f"{text[: limit - 1]}…"


def compact_step_inspector(run: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Build the compact, HTML-safe data model consumed by the runs dashboard."""
    if not run:
        return None
    raw_steps = run.get("steps")
    steps: list[dict[str, Any]] = []
    if isinstance(raw_steps, list):
        for index, item in enumerate(raw_steps, start=1):
            if not isinstance(item, Mapping):
                continue
            result = item.get("result_preview", item.get("result"))
            steps.append(
                {
                    "id": item.get("id", index),
                    "title": item.get("title") or item.get("name") or f"Step {index}",
                    "tool": item.get("tool") or item.get("action") or "",
                    "status": item.get("status") or "unknown",
                    "error": _preview(item.get("error")),
                    "result_preview": _preview(result),
                }
            )

    artifacts = run.get("artifacts")
    artifact_count = len(artifacts) if isinstance(artifacts, (list, tuple, dict, set)) else 0
    return {
        "run_id": run.get("run_id") or run.get("id") or "",
        "task": run.get("task") or run.get("title") or "",
        "status": run.get("status") or "unknown",
        "profile": run_profile(run),
        "steps": steps,
        "step_count": len(steps),
        "artifact_count": artifact_count,
    }
