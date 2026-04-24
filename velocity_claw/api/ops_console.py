from __future__ import annotations


def build_operations_console(*, release_state: dict, queue_jobs: list[dict], approvals: list[dict], provider_observability: dict, last_failed: dict | None, metrics: dict, active_workers: int, max_concurrency: int) -> dict:
    return {
        "status": "ok",
        "release": {
            "readiness": release_state.get("readiness"),
            "score": release_state.get("score"),
            "total_checks": release_state.get("total_checks"),
            "blocking_issues": len(release_state.get("blocking_issues", [])),
            "warnings": len(release_state.get("warnings", [])),
        },
        "queue": {
            "total": len(queue_jobs),
            "running": sum(1 for job in queue_jobs if job.get("status") == "running"),
            "failed": sum(1 for job in queue_jobs if job.get("status") == "failed"),
            "cancelled": sum(1 for job in queue_jobs if job.get("status") == "cancelled"),
            "active_workers": active_workers,
            "max_concurrency": max_concurrency,
        },
        "approvals": {
            "pending": len(approvals),
        },
        "providers": provider_observability.get("summary", {}),
        "last_failed_run": {
            "run_id": last_failed.get("run_id"),
            "task": last_failed.get("task"),
            "status": last_failed.get("status"),
        } if last_failed else None,
        "metrics": metrics,
    }
