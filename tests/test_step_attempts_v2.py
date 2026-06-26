import sqlite3
from pathlib import Path

from velocity_claw.config.settings import Settings
from velocity_claw.memory import MemoryStore
from velocity_claw.memory.step_attempts_v2 import attempt_summary, effective_steps


def settings_for(tmp_path: Path, monkeypatch) -> Settings:
    monkeypatch.setenv("VELOCITY_CLAW_ENV", "test")
    monkeypatch.setenv("VELOCITY_CLAW_MEMORY_DB_PATH", str(tmp_path / "memory.db"))
    return Settings()


def step(step_id, status, *, attempt_no=1, phase="initial", error=None):
    return {
        "id": step_id,
        "title": f"Step {step_id}",
        "tool": "analysis",
        "args": {"prompt": "inspect"},
        "status": status,
        "result": {"attempt": attempt_no} if status == "success" else None,
        "error": error,
        "started_at": f"2026-06-26T10:00:0{attempt_no}",
        "completed_at": f"2026-06-26T10:00:1{attempt_no}",
        "attempt_no": attempt_no,
        "phase": phase,
    }


def test_existing_steps_table_is_migrated_without_losing_history(tmp_path: Path, monkeypatch):
    settings = settings_for(tmp_path, monkeypatch)
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
            """
            CREATE TABLE steps (
                id INTEGER PRIMARY KEY,
                run_id TEXT NOT NULL,
                step_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                tool TEXT,
                args TEXT,
                status TEXT NOT NULL,
                result TEXT,
                error TEXT,
                started_at DATETIME,
                completed_at DATETIME
            )
            """
        )
        conn.execute(
            "INSERT INTO runs (run_id, task, status) VALUES (?, ?, ?)",
            ("legacy-run", "Legacy run", "failed"),
        )
        conn.execute(
            """
            INSERT INTO steps (
                run_id, step_id, title, tool, args, status, result, error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("legacy-run", 1, "Legacy step", "analysis", "{}", "failed", None, "boom"),
        )

    memory = MemoryStore(settings)
    loaded = memory.load_steps("legacy-run")

    with sqlite3.connect(settings.memory_db_path) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(steps)").fetchall()}

    assert {"attempt_no", "phase"}.issubset(columns)
    assert loaded[0]["status"] == "failed"
    assert loaded[0]["attempt_no"] == 1
    assert loaded[0]["phase"] == "initial"


def test_multiple_attempts_are_preserved_and_effective_state_uses_latest(tmp_path: Path, monkeypatch):
    memory = MemoryStore(settings_for(tmp_path, monkeypatch))
    run_id = memory.create_run("Resume failed step")
    memory.save_step(run_id, step(1, "success"))
    memory.save_step(run_id, step(2, "failed", error="first failure"))
    memory.save_step(run_id, step(2, "success", attempt_no=2, phase="failed_resume"))
    memory.save_step(run_id, step(3, "success", attempt_no=1, phase="failed_resume"))
    memory.update_run_status(run_id, "completed")

    run = memory.load_run(run_id)
    records = run["steps"]
    latest = effective_steps(records)

    assert len(records) == 4
    assert [item["id"] for item in latest] == [1, 2, 3]
    assert next(item for item in latest if item["id"] == 2)["status"] == "success"
    assert run["forensics"]["failed_step"] is None
    assert run["forensics"]["step_attempts"]["retried_steps"] == ["2"]
    assert run["report"]["step_overview"]["failed"] == 0
    assert run["report"]["step_attempt_overview"]["total_attempt_records"] == 4


def test_update_step_status_changes_only_latest_attempt(tmp_path: Path, monkeypatch):
    memory = MemoryStore(settings_for(tmp_path, monkeypatch))
    run_id = memory.create_run("Approval attempt")
    memory.save_step(run_id, step(2, "failed", error="old failure"))
    memory.save_step(run_id, step(2, "pending_approval", attempt_no=2, phase="failed_resume"))

    memory.update_step_status(run_id, 2, "approved", result={"decision": "approved"})
    records = memory.load_steps(run_id)

    assert records[0]["status"] == "failed"
    assert records[0]["error"] == "old failure"
    assert records[1]["status"] == "approved"
    assert records[1]["attempt_no"] == 2
    assert records[1]["phase"] == "failed_resume"


def test_attempt_summary_counts_phases_and_retries():
    records = [
        step(1, "success"),
        step(2, "failed"),
        step(2, "success", attempt_no=2, phase="failed_resume"),
    ]

    summary = attempt_summary(records)

    assert summary["total_attempt_records"] == 3
    assert summary["unique_steps"] == 2
    assert summary["retried_steps"] == ["2"]
    assert summary["attempts_by_step"] == {"1": 1, "2": 2}
    assert summary["records_by_phase"] == {"initial": 2, "failed_resume": 1}
