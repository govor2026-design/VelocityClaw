from __future__ import annotations

import sqlite3
from typing import Any


PROFILE_ARTIFACT_NAME = "run_execution_profile"
PROFILE_ARTIFACT_TYPE = "metadata"
UNKNOWN_PROFILE = "unknown"


def _normalize_profile(value: Any) -> str:
    profile = str(value or "").strip().lower()
    return profile or UNKNOWN_PROFILE


def _profile_from_artifacts(artifacts: list[dict[str, Any]]) -> str:
    for artifact in reversed(artifacts or []):
        if artifact.get("name") == PROFILE_ARTIFACT_NAME:
            return _normalize_profile(artifact.get("content"))
    return UNKNOWN_PROFILE


def _profiles_for_runs(memory: Any, run_ids: list[str]) -> dict[str, str]:
    if not run_ids or not getattr(memory, "enabled", False):
        return {}
    placeholders = ",".join("?" for _ in run_ids)
    query = (
        "SELECT run_id, content FROM artifacts "
        f"WHERE name = ? AND run_id IN ({placeholders}) ORDER BY id DESC"
    )
    profiles: dict[str, str] = {}
    with sqlite3.connect(memory.db_path) as conn:
        for run_id, content in conn.execute(query, [PROFILE_ARTIFACT_NAME, *run_ids]).fetchall():
            profiles.setdefault(run_id, _normalize_profile(content))
    return profiles


def install_run_profile_v2(memory_cls: type) -> None:
    """Add backward-compatible run profile metadata to ``MemoryStore``.

    Profiles are persisted as run-level metadata artifacts, avoiding a destructive
    schema change for existing installations. Historical runs without the artifact
    are exposed as ``unknown``.
    """
    if getattr(memory_cls, "_run_profile_v2_installed", False):
        return

    original_create_run = memory_cls.create_run
    original_load_run = memory_cls.load_run
    original_list_recent_runs = memory_cls.list_recent_runs

    def create_run(self, task: str, execution_profile: str | None = None) -> str:
        run_id = original_create_run(self, task)
        profile = _normalize_profile(execution_profile or getattr(self.settings, "execution_profile", None))
        if getattr(self, "enabled", False):
            self.save_artifact(
                run_id,
                PROFILE_ARTIFACT_NAME,
                profile,
                artifact_type=PROFILE_ARTIFACT_TYPE,
            )
        return run_id

    def load_run(self, run_id: str):
        run = original_load_run(self, run_id)
        if run is not None:
            run["execution_profile"] = _profile_from_artifacts(run.get("artifacts") or [])
        return run

    def list_recent_runs(self, limit: int = 20):
        runs = original_list_recent_runs(self, limit=limit)
        profiles = _profiles_for_runs(self, [item.get("run_id") for item in runs if item.get("run_id")])
        for run in runs:
            run["execution_profile"] = profiles.get(run.get("run_id"), UNKNOWN_PROFILE)
        return runs

    memory_cls.create_run = create_run
    memory_cls.load_run = load_run
    memory_cls.list_recent_runs = list_recent_runs
    memory_cls._run_profile_v2_installed = True
