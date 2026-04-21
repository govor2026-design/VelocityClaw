from __future__ import annotations

from dataclasses import dataclass, asdict
from threading import Lock


@dataclass
class MetricsState:
    tasks_total: int = 0
    tasks_failed: int = 0
    tasks_completed: int = 0
    auto_fix_total: int = 0
    approvals_pending: int = 0
    queue_total: int = 0
    queue_running: int = 0
    queue_failed: int = 0
    queue_cancelled: int = 0
    total_task_duration_ms: int = 0
    task_duration_samples: int = 0


class MetricsRegistry:
    def __init__(self):
        self._state = MetricsState()
        self._lock = Lock()

    def incr(self, field: str, amount: int = 1) -> None:
        with self._lock:
            setattr(self._state, field, getattr(self._state, field) + amount)

    def set_value(self, field: str, value: int) -> None:
        with self._lock:
            setattr(self._state, field, value)

    def observe_task_duration(self, duration_ms: int) -> None:
        with self._lock:
            self._state.total_task_duration_ms += duration_ms
            self._state.task_duration_samples += 1

    def snapshot(self) -> dict:
        with self._lock:
            data = asdict(self._state)
        samples = data.get("task_duration_samples", 0)
        total = data.get("total_task_duration_ms", 0)
        data["avg_task_duration_ms"] = int(total / samples) if samples else 0
        return data

    def diagnostics_summary(self) -> dict:
        snapshot = self.snapshot()
        return {
            "task_health": {
                "total": snapshot["tasks_total"],
                "completed": snapshot["tasks_completed"],
                "failed": snapshot["tasks_failed"],
                "avg_duration_ms": snapshot["avg_task_duration_ms"],
            },
            "queue_health": {
                "total": snapshot["queue_total"],
                "running": snapshot["queue_running"],
                "failed": snapshot["queue_failed"],
                "cancelled": snapshot["queue_cancelled"],
            },
            "approvals_pending": snapshot["approvals_pending"],
            "auto_fix_total": snapshot["auto_fix_total"],
        }
