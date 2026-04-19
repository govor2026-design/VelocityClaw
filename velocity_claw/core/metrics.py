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

    def snapshot(self) -> dict:
        with self._lock:
            return asdict(self._state)
