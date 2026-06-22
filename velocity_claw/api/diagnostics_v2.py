from __future__ import annotations

from typing import Any

from velocity_claw.__version__ import __product_name__, __release_stage__, __version__


def _queue_summary(
    queue_jobs: list[dict[str, Any]],
    active_workers: int,
    max_concurrency: int,
    queue_runtime: dict[str, Any] | None = None,
) -> dict[str, Any]:
    runtime = queue_runtime or {}
    startup_recovery = runtime.get("startup_recovery") or {}
    return {
        "total": len(queue_jobs),
        "running": sum(1 for job in queue_jobs if job.get("status") == "running"),
        "queued": sum(1 for job in queue_jobs if job.get("status") == "queued"),
        "completed": sum(1 for job in queue_jobs if job.get("status") == "completed"),
        "failed": sum(1 for job in queue_jobs if job.get("status") == "failed"),
        "cancelled": sum(1 for job in queue_jobs if job.get("status") == "cancelled"),
        "orchestrator": runtime.get("orchestrator"),
        "accepting_work": runtime.get("accepting_work", True),
        "active_workers": active_workers,
        "scheduled_workers": runtime.get("scheduled_workers", 0),
        "tracked_tasks": runtime.get("tracked_tasks", 0),
        "active_slots": runtime.get("active_slots", {}),
        "available_slots": runtime.get("available_slots"),
        "scheduling_capacity": runtime.get("scheduling_capacity"),
        "max_concurrency": runtime.get("max_concurrency", max_concurrency),
        "max_attempts": runtime.get("max_attempts"),
        "persistence_enabled": runtime.get("persistence_enabled", False),
        "recover_on_startup": runtime.get("recover_on_startup", False),
        "startup_recovery": startup_recovery,
    }


def _provider_summary(provider_health: dict[str, dict[str, Any]]) -> dict[str, Any]:
    total = len(provider_health)
    in_cooldown = [name for name, state in provider_health.items() if state.get("in_cooldown")]
    failed = [name for name, state in provider_health.items() if state.get("failures", 0) > 0]
    return {
        "total": total,
        "in_cooldown": len(in_cooldown),
        "failed": len(failed),
        "cooldown_providers": in_cooldown,
        "providers_with_failures": failed,
    }


def _risk_flags(*, settings: Any, release_state: dict[str, Any], queue: dict[str, Any], approvals: list[dict[str, Any]], provider_summary: dict[str, Any], last_failed: dict[str, Any] | None) -> list[dict[str, str]]:
    flags: list[dict[str, str]] = []
    if getattr(settings, "trusted_mode", False):
        flags.append({"level": "high", "code": "trusted_mode_enabled", "message": "Trusted mode is enabled."})
    if getattr(settings, "shell_enabled", False):
        flags.append({"level": "medium", "code": "shell_enabled", "message": "Shell execution is enabled."})
    if getattr(settings, "git_enabled", False):
        flags.append({"level": "medium", "code": "git_enabled", "message": "Git execution is enabled."})
    if release_state.get("readiness") not in {"ready", "ok"}:
        flags.append({"level": "medium", "code": "release_not_ready", "message": "Release readiness is not green."})
    if queue.get("failed", 0) > 0:
        flags.append({"level": "medium", "code": "queue_failures", "message": "Queue has failed jobs."})
    if not queue.get("accepting_work", True):
        flags.append({"level": "info", "code": "queue_not_accepting_work", "message": "Queue orchestration is paused or draining."})
    recovery = queue.get("startup_recovery") or {}
    if recovery.get("recovered_running", 0) > 0:
        flags.append({"level": "info", "code": "queue_restart_recovery", "message": "Interrupted queue jobs were recovered after restart."})
    if recovery.get("invalid_failed", 0) > 0:
        flags.append({"level": "medium", "code": "queue_invalid_persisted_state", "message": "Invalid persisted queue states were failed during recovery."})
    if approvals:
        flags.append({"level": "info", "code": "pending_approvals", "message": "There are pending approvals."})
    if provider_summary.get("in_cooldown", 0) > 0:
        flags.append({"level": "medium", "code": "provider_cooldown", "message": "One or more providers are in cooldown."})
    if last_failed:
        flags.append({"level": "info", "code": "last_failed_run", "message": "A failed run is available for inspection."})
    return flags


def build_diagnostics_v2(
    *,
    settings: Any,
    release_state: dict[str, Any],
    queue_jobs: list[dict[str, Any]],
    approvals: list[dict[str, Any]],
    provider_observability: dict[str, Any],
    provider_health: dict[str, dict[str, Any]],
    last_failed: dict[str, Any] | None,
    metrics: dict[str, Any],
    active_workers: int,
    max_concurrency: int,
    queue_runtime: dict[str, Any] | None = None,
) -> dict[str, Any]:
    queue = _queue_summary(queue_jobs, active_workers, max_concurrency, queue_runtime)
    providers = _provider_summary(provider_health)
    flags = _risk_flags(
        settings=settings,
        release_state=release_state,
        queue=queue,
        approvals=approvals,
        provider_summary=providers,
        last_failed=last_failed,
    )
    return {
        "status": "ok",
        "version": {
            "product": __product_name__,
            "version": __version__,
            "release_stage": __release_stage__,
        },
        "summary": {
            "release_readiness": release_state.get("readiness"),
            "release_score": release_state.get("score"),
            "release_total_checks": release_state.get("total_checks"),
            "queue_total": queue["total"],
            "queue_running": queue["running"],
            "queue_queued": queue["queued"],
            "queue_failed": queue["failed"],
            "queue_scheduled": queue["scheduled_workers"],
            "queue_tracked_tasks": queue["tracked_tasks"],
            "queue_accepting_work": queue["accepting_work"],
            "queue_recovered_running": (queue.get("startup_recovery") or {}).get("recovered_running", 0),
            "approvals_pending": len(approvals),
            "provider_failures": providers["failed"],
            "provider_cooldowns": providers["in_cooldown"],
            "risk_flags": len(flags),
        },
        "runtime": {
            "env": getattr(settings, "env", None),
            "execution_profile": getattr(settings, "execution_profile", None),
            "safe_mode": getattr(settings, "safe_mode", None),
            "trusted_mode": getattr(settings, "trusted_mode", None),
            "shell_enabled": getattr(settings, "shell_enabled", None),
            "git_enabled": getattr(settings, "git_enabled", None),
            "dry_run": getattr(settings, "dry_run", None),
        },
        "release": {
            "readiness": release_state.get("readiness"),
            "score": release_state.get("score"),
            "total_checks": release_state.get("total_checks"),
            "blocking_issues": release_state.get("blocking_issues", []),
            "warnings": release_state.get("warnings", []),
        },
        "queue": queue,
        "approvals": {
            "pending": len(approvals),
            "items": approvals[:10],
        },
        "providers": {
            "summary": providers,
            "router": provider_observability.get("summary", {}) if isinstance(provider_observability, dict) else {},
            "health": provider_health,
        },
        "last_failed_run": last_failed,
        "metrics": metrics,
        "risk_flags": flags,
        "links": {
            "version": "/version",
            "dashboard_v2": "/dashboard/v2",
            "diagnostics_v2": "/diagnostics/v2",
            "queue_runtime_v2": "/queue/v2/runtime",
            "queue_pause_v2": "/queue/v2/pause",
            "queue_resume_v2": "/queue/v2/resume",
            "queue_drain_v2": "/queue/v2/drain",
            "ops_console": "/ops/console",
            "runs": "/runs",
            "approvals": "/approvals",
            "providers": "/providers/observability",
            "release_readiness": "/release/readiness",
        },
    }
