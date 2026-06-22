from __future__ import annotations

import sqlite3
from typing import Any


UNKNOWN_PROFILE = "unknown"


def normalize_profile(value: Any) -> str:
    profile = str(value or "").strip().lower()
    return profile or UNKNOWN_PROFILE


def install_run_profile_schema(memory_cls: type) -> None:
    """Persist execution profile directly on the existing ``runs`` table.

    The installer is applied before ``MemoryStore`` instances are created. Existing
    databases are migrated in place with a non-destructive column addition, while
    historical rows are exposed as ``unknown``.
    """
    if getattr(memory_cls, "_run_profile_schema_installed", False):
        return

    original_ensure_tables = memory_cls._ensure_tables
    original_create_run = memory_cls.create_run
    original_load_run = memory_cls.load_run
    original_list_recent_runs = memory_cls.list_recent_runs

    def _ensure_tables(self) -> None:
        original_ensure_tables(self)
        if not getattr(self, "enabled", False):
            return
        with sqlite3.connect(self.db_path) as conn:
            columns = {row[1] for row in conn.execute("PRAGMA table_info(runs)").fetchall()}
            if "execution_profile" not in columns:
                conn.execute(
                    "ALTER TABLE runs ADD COLUMN execution_profile TEXT NOT NULL DEFAULT 'unknown'"
                )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_runs_execution_profile_created_at "
                "ON runs(execution_profile, created_at)"
            )

    def create_run(self, task: str, execution_profile: str | None = None) -> str:
        run_id = original_create_run(self, task)
        if not getattr(self, "enabled", False):
            return run_id
        profile = normalize_profile(
            execution_profile or getattr(getattr(self, "settings", None), "execution_profile", None)
        )
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE runs SET execution_profile = ? WHERE run_id = ?",
                (profile, run_id),
            )
        return run_id

    def load_run(self, run_id: str):
        run = original_load_run(self, run_id)
        if run is None:
            return None
        profile = UNKNOWN_PROFILE
        if getattr(self, "enabled", False):
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute(
                    "SELECT execution_profile FROM runs WHERE run_id = ?",
                    (run_id,),
                ).fetchone()
            if row:
                profile = normalize_profile(row[0])
        run["execution_profile"] = profile
        return run

    def list_recent_runs(self, limit: int = 20):
        runs = original_list_recent_runs(self, limit=limit)
        if not runs or not getattr(self, "enabled", False):
            for run in runs:
                run["execution_profile"] = normalize_profile(run.get("execution_profile"))
            return runs

        run_ids = [run.get("run_id") for run in runs if run.get("run_id")]
        placeholders = ",".join("?" for _ in run_ids)
        profiles: dict[str, str] = {}
        if run_ids:
            with sqlite3.connect(self.db_path) as conn:
                rows = conn.execute(
                    f"SELECT run_id, execution_profile FROM runs WHERE run_id IN ({placeholders})",
                    run_ids,
                ).fetchall()
            profiles = {run_id: normalize_profile(profile) for run_id, profile in rows}

        for run in runs:
            run["execution_profile"] = profiles.get(run.get("run_id"), UNKNOWN_PROFILE)
        return runs

    memory_cls._ensure_tables = _ensure_tables
    memory_cls.create_run = create_run
    memory_cls.load_run = load_run
    memory_cls.list_recent_runs = list_recent_runs
    memory_cls._run_profile_schema_installed = True
