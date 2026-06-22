import sqlite3
from pathlib import Path

from velocity_claw.config.settings import Settings
from velocity_claw.memory.context_v2 import ProjectContextV2  # noqa: F401 - installs profile schema
from velocity_claw.memory.store import MemoryStore


def build_settings(tmp_path: Path, monkeypatch, profile: str = "dev") -> Settings:
    monkeypatch.setenv("VELOCITY_CLAW_ENV", "test")
    monkeypatch.setenv("VELOCITY_CLAW_MEMORY_DB_PATH", str(tmp_path / "memory.db"))
    monkeypatch.setenv("VELOCITY_CLAW_EXECUTION_PROFILE", profile)
    return Settings()


def test_existing_runs_table_is_migrated_without_losing_rows(tmp_path: Path, monkeypatch):
    settings = build_settings(tmp_path, monkeypatch, profile="safe")
    with sqlite3.connect(settings.memory_db_path) as conn:
        conn.execute(
            """
            CREATE TABLE runs (
                run_id TEXT PRIMARY KEY,
                task TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                completed_at DATETIME
            )
            """
        )
        conn.execute(
            "INSERT INTO runs (run_id, task, status) VALUES (?, ?, ?)",
            ("legacy-run", "Legacy task", "completed"),
        )

    memory = MemoryStore(settings)

    with sqlite3.connect(settings.memory_db_path) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(runs)").fetchall()}
        profile = conn.execute(
            "SELECT execution_profile FROM runs WHERE run_id = ?",
            ("legacy-run",),
        ).fetchone()[0]

    assert "execution_profile" in columns
    assert profile == "unknown"
    assert memory.load_run("legacy-run")["execution_profile"] == "unknown"


def test_new_run_persists_active_execution_profile(tmp_path: Path, monkeypatch):
    memory = MemoryStore(build_settings(tmp_path, monkeypatch, profile="dev"))

    run_id = memory.create_run("Inspect dashboard")
    summary = memory.list_recent_runs(limit=10)[0]
    loaded = memory.load_run(run_id)

    assert summary["execution_profile"] == "dev"
    assert loaded["execution_profile"] == "dev"
    assert all(artifact.get("name") != "run_execution_profile" for artifact in loaded["artifacts"])


def test_explicit_profile_override_is_normalized(tmp_path: Path, monkeypatch):
    memory = MemoryStore(build_settings(tmp_path, monkeypatch, profile="safe"))

    run_id = memory.create_run("Owner operation", execution_profile=" OWNER ")

    assert memory.load_run(run_id)["execution_profile"] == "owner"


def test_recent_runs_are_enriched_in_one_compatible_response(tmp_path: Path, monkeypatch):
    memory = MemoryStore(build_settings(tmp_path, monkeypatch, profile="safe"))
    safe_run = memory.create_run("Safe run")
    owner_run = memory.create_run("Owner run", execution_profile="owner")

    summaries = {item["run_id"]: item for item in memory.list_recent_runs(limit=10)}

    assert summaries[safe_run]["execution_profile"] == "safe"
    assert summaries[owner_run]["execution_profile"] == "owner"
