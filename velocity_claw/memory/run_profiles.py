from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


class RunProfileStore:
    def __init__(self, db_path: str | None):
        self.db_path = db_path
        if self.db_path:
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
            self._ensure_table()

    def _ensure_table(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS run_profiles (
                    run_id TEXT PRIMARY KEY,
                    execution_profile TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_run_profiles_profile "
                "ON run_profiles(execution_profile, created_at)"
            )

    def record(self, run_id: str, execution_profile: str) -> None:
        if not self.db_path or not run_id:
            return
        profile = str(execution_profile or "unknown").strip().lower() or "unknown"
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO run_profiles (run_id, execution_profile, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    execution_profile = excluded.execution_profile
                """,
                (run_id, profile, datetime.now().isoformat()),
            )

    def get(self, run_id: str) -> str | None:
        if not self.db_path:
            return None
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT execution_profile FROM run_profiles WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        return row[0] if row else None

    def get_many(self, run_ids: list[str]) -> dict[str, str]:
        ids = [run_id for run_id in run_ids if run_id]
        if not self.db_path or not ids:
            return {}
        placeholders = ",".join("?" for _ in ids)
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                f"SELECT run_id, execution_profile FROM run_profiles WHERE run_id IN ({placeholders})",
                ids,
            ).fetchall()
        return {row[0]: row[1] for row in rows}

    def list_profiles(self) -> list[str]:
        if not self.db_path:
            return []
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT DISTINCT execution_profile FROM run_profiles ORDER BY execution_profile"
            ).fetchall()
        return [row[0] for row in rows]


def install_run_profile_tracking(agent: Any) -> RunProfileStore:
    """Record profiles for future runs and enrich existing memory reads.

    The adapter is installed once and preserves the public MemoryStore method
    signatures. Historical rows without metadata are reported as ``unknown``.
    """
    existing = getattr(agent, "run_profiles", None)
    if existing is not None:
        return existing

    memory = agent.memory
    store = RunProfileStore(getattr(memory, "db_path", None))
    original_create_run = memory.create_run
    original_list_recent_runs = memory.list_recent_runs
    original_load_run = memory.load_run

    def create_run(task: str) -> str:
        run_id = original_create_run(task)
        store.record(run_id, getattr(agent.settings, "execution_profile", "unknown"))
        return run_id

    def list_recent_runs(limit: int = 20):
        runs = original_list_recent_runs(limit=limit)
        profiles = store.get_many([item.get("run_id") for item in runs])
        return [
            {
                **item,
                "execution_profile": profiles.get(item.get("run_id"), "unknown"),
            }
            for item in runs
        ]

    def load_run(run_id: str):
        run = original_load_run(run_id)
        if run is not None:
            run["execution_profile"] = store.get(run_id) or "unknown"
        return run

    memory.create_run = create_run
    memory.list_recent_runs = list_recent_runs
    memory.load_run = load_run
    agent.run_profiles = store
    return store
