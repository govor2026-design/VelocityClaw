from __future__ import annotations

import json
import sqlite3
from collections import Counter
from datetime import datetime
from typing import Any


def effective_steps(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[Any, dict[str, Any]] = {}
    order: list[Any] = []
    for index, step in enumerate(steps):
        step_id = step.get("id")
        key = step_id if step_id is not None else f"record:{step.get('record_id', index)}"
        if key not in latest:
            order.append(key)
        latest[key] = step
    return [latest[key] for key in order]


def attempt_summary(steps: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter(str(step.get("id")) for step in steps if step.get("id") is not None)
    phases = Counter(str(step.get("phase") or "initial") for step in steps)
    latest = effective_steps(steps)
    return {
        "total_attempt_records": len(steps),
        "unique_steps": len(latest),
        "retried_steps": sorted(step_id for step_id, count in counts.items() if count > 1),
        "attempts_by_step": dict(counts),
        "records_by_phase": dict(phases),
    }


def install_step_attempts_v2(memory_cls: type) -> None:
    if getattr(memory_cls, "_step_attempts_v2_installed", False):
        return

    original_ensure_tables = memory_cls._ensure_tables
    original_build_forensics = memory_cls.build_run_forensics
    original_build_report = memory_cls.build_run_report

    def _ensure_tables(self) -> None:
        original_ensure_tables(self)
        if not getattr(self, "enabled", False):
            return
        with sqlite3.connect(self.db_path) as conn:
            columns = {row[1] for row in conn.execute("PRAGMA table_info(steps)").fetchall()}
            if "attempt_no" not in columns:
                conn.execute("ALTER TABLE steps ADD COLUMN attempt_no INTEGER NOT NULL DEFAULT 1")
            if "phase" not in columns:
                conn.execute("ALTER TABLE steps ADD COLUMN phase TEXT NOT NULL DEFAULT 'initial'")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_steps_run_step_attempt "
                "ON steps(run_id, step_id, attempt_no, id)"
            )

    def save_step(self, run_id: str, step: dict, attempt_no: int | None = None, phase: str | None = None) -> None:
        if not getattr(self, "enabled", False):
            return
        resolved_attempt = attempt_no if attempt_no is not None else step.get("attempt_no", 1)
        try:
            resolved_attempt = max(1, int(resolved_attempt))
        except (TypeError, ValueError):
            resolved_attempt = 1
        resolved_phase = str(phase or step.get("phase") or "initial").strip() or "initial"
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO steps (
                    run_id, step_id, title, tool, args, status, result, error,
                    started_at, completed_at, attempt_no, phase
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    step.get("id"),
                    step.get("title"),
                    step.get("tool"),
                    json.dumps(step.get("args", {}), ensure_ascii=False),
                    step.get("status"),
                    json.dumps(step.get("result"), ensure_ascii=False),
                    step.get("error"),
                    step.get("started_at"),
                    step.get("completed_at"),
                    resolved_attempt,
                    resolved_phase,
                ),
            )

    def load_steps(self, run_id: str):
        if not getattr(self, "enabled", False):
            return []
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT id, step_id, title, tool, args, status, result, error,
                       started_at, completed_at, attempt_no, phase
                FROM steps
                WHERE run_id = ?
                ORDER BY id
                """,
                (run_id,),
            ).fetchall()
        return [
            {
                "record_id": row[0],
                "id": row[1],
                "title": row[2],
                "tool": row[3],
                "args": json.loads(row[4]) if row[4] else {},
                "status": row[5],
                "result": json.loads(row[6]) if row[6] is not None else None,
                "error": row[7],
                "started_at": row[8],
                "completed_at": row[9],
                "attempt_no": row[10] or 1,
                "phase": row[11] or "initial",
            }
            for row in rows
        ]

    def update_step_status(self, run_id: str, step_id: int, status: str, result: Any = None, error: str | None = None) -> None:
        if not getattr(self, "enabled", False):
            return
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE steps
                SET status = ?, result = ?, error = ?, completed_at = ?
                WHERE id = (
                    SELECT id FROM steps
                    WHERE run_id = ? AND step_id = ?
                    ORDER BY id DESC LIMIT 1
                )
                """,
                (
                    status,
                    json.dumps(result, ensure_ascii=False) if result is not None else None,
                    error,
                    datetime.now().isoformat(),
                    run_id,
                    step_id,
                ),
            )

    def build_run_forensics(self, run: dict) -> dict:
        steps = run.get("steps", [])
        effective = effective_steps(steps)
        payload = original_build_forensics(self, {**run, "steps": effective, "forensics": None})
        payload["step_attempts"] = attempt_summary(steps)
        payload["latest_effective_steps"] = [
            {
                "id": step.get("id"),
                "status": step.get("status"),
                "attempt_no": step.get("attempt_no", 1),
                "phase": step.get("phase", "initial"),
            }
            for step in effective
        ]
        return payload

    def build_run_report(self, run: dict) -> dict:
        steps = run.get("steps", [])
        effective = effective_steps(steps)
        payload = original_build_report(self, {**run, "steps": effective, "forensics": None, "report": None})
        payload["step_attempt_overview"] = attempt_summary(steps)
        return payload

    memory_cls._ensure_tables = _ensure_tables
    memory_cls.save_step = save_step
    memory_cls.load_steps = load_steps
    memory_cls.update_step_status = update_step_status
    memory_cls.build_run_forensics = build_run_forensics
    memory_cls.build_run_report = build_run_report
    memory_cls._step_attempts_v2_installed = True
