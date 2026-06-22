import sqlite3
from pathlib import Path

from velocity_claw.config.settings import Settings
from velocity_claw.memory.context_v2 import ProjectContextV2  # noqa: F401 - installs MemoryStore profile support
from velocity_claw.memory.store import MemoryStore


def build_memory(tmp_path: Path, monkeypatch, profile: str = "dev") -> MemoryStore:
    monkeypatch.setenv("VELOCITY_CLAW_ENV", "test")
    monkeypatch.setenv("VELOCITY_CLAW_MEMORY_DB_PATH", str(tmp_path / "memory.db"))
    monkeypatch.setenv("VELOCITY_CLAW_EXECUTION_PROFILE", profile)
    return MemoryStore(Settings())


def test_run_profile_is_persisted_and_exposed(tmp_path: Path, monkeypatch):
    memory = build_memory(tmp_path, monkeypatch, profile="dev")

    run_id = memory.create_run("Inspect dashboard filters")
    summary = memory.list_recent_runs(limit=10)[0]
    loaded = memory.load_run(run_id)

    assert summary["execution_profile"] == "dev"
    assert loaded["execution_profile"] == "dev"
    metadata = [item for item in loaded["artifacts"] if item["name"] == "run_execution_profile"]
    assert len(metadata) == 1
    assert metadata[0]["artifact_type"] == "metadata"
    assert metadata[0]["content"] == "dev"


def test_explicit_profile_override_is_normalized(tmp_path: Path, monkeypatch):
    memory = build_memory(tmp_path, monkeypatch, profile="safe")

    run_id = memory.create_run("Owner workflow", execution_profile=" OWNER ")

    assert memory.load_run(run_id)["execution_profile"] == "owner"


def test_legacy_run_without_profile_is_exposed_as_unknown(tmp_path: Path, monkeypatch):
    memory = build_memory(tmp_path, monkeypatch, profile="safe")
    legacy_id = "legacy-run"
    with sqlite3.connect(memory.db_path) as conn:
        conn.execute(
            "INSERT INTO runs (run_id, task, status) VALUES (?, ?, ?)",
            (legacy_id, "Legacy task", "completed"),
        )

    summaries = {item["run_id"]: item for item in memory.list_recent_runs(limit=20)}

    assert summaries[legacy_id]["execution_profile"] == "unknown"
    assert memory.load_run(legacy_id)["execution_profile"] == "unknown"
