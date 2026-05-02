import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from velocity_claw.config.settings import Settings
from velocity_claw.memory.store import MemoryStore


def make_store(tmp_path):
    settings = Settings(
        env="test",
        memory_enabled=True,
        memory_db_path=str(tmp_path / "memory.db"),
        memory_retention_days=30,
        memory_retention_min_runs=2,
        memory_cleanup_vacuum=False,
    )
    return MemoryStore(settings)


def insert_run(conn, run_id, created_at):
    conn.execute(
        "INSERT INTO runs (run_id, task, status, created_at, completed_at) VALUES (?, ?, ?, ?, ?)",
        (run_id, f"task {run_id}", "completed", created_at, created_at),
    )
    conn.execute(
        "INSERT INTO steps (run_id, step_id, title, status) VALUES (?, ?, ?, ?)",
        (run_id, 1, "step", "success"),
    )
    conn.execute(
        "INSERT INTO artifacts (run_id, step_id, name, content) VALUES (?, ?, ?, ?)",
        (run_id, 1, "artifact", "content"),
    )
    conn.execute(
        "INSERT INTO fix_attempts (run_id, attempt_no, summary, created_at) VALUES (?, ?, ?, ?)",
        (run_id, 1, "{}", created_at),
    )
    conn.execute(
        "INSERT INTO approval_history (run_id, step_id, decision, created_at) VALUES (?, ?, ?, ?)",
        (run_id, 1, "approved", created_at),
    )


def count_rows(db_path, table):
    with sqlite3.connect(db_path) as conn:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_cleanup_retention_deletes_old_runs_and_children(tmp_path):
    store = make_store(tmp_path)
    now = datetime.utcnow()
    old = (now - timedelta(days=90)).isoformat()
    fresh = now.isoformat()
    with sqlite3.connect(store.db_path) as conn:
        insert_run(conn, "old-1", old)
        insert_run(conn, "old-2", old)
        insert_run(conn, "new-1", fresh)
        insert_run(conn, "new-2", fresh)
        conn.execute("INSERT INTO project_notes (note_type, content, created_at) VALUES (?, ?, ?)", ("note", "old", old))

    result = store.cleanup_retention(days=30, keep_min_runs=2, vacuum=False)

    assert result["status"] == "ok"
    assert result["deleted"]["runs"] == 2
    assert count_rows(store.db_path, "runs") == 2
    assert count_rows(store.db_path, "steps") == 2
    assert count_rows(store.db_path, "artifacts") == 2
    assert count_rows(store.db_path, "fix_attempts") == 2
    assert count_rows(store.db_path, "approval_history") == 2
    assert count_rows(store.db_path, "project_notes") == 0


def test_cleanup_retention_keeps_minimum_newest_runs_even_when_old(tmp_path):
    store = make_store(tmp_path)
    old = (datetime.utcnow() - timedelta(days=90)).isoformat()
    with sqlite3.connect(store.db_path) as conn:
        insert_run(conn, "old-1", old)
        insert_run(conn, "old-2", old)

    result = store.cleanup_retention(days=30, keep_min_runs=2, vacuum=False)

    assert result["deleted"]["runs"] == 0
    assert count_rows(store.db_path, "runs") == 2


def test_memory_retention_settings_are_loaded_from_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("ENV", "test")
    monkeypatch.setenv("MEMORY_DB_PATH", str(tmp_path / "memory.db"))
    monkeypatch.setenv("MEMORY_RETENTION_DAYS", "14")
    monkeypatch.setenv("MEMORY_RETENTION_MIN_RUNS", "3")
    monkeypatch.setenv("MEMORY_CLEANUP_VACUUM", "false")
    settings = Settings()
    assert settings.memory_retention_days == 14
    assert settings.memory_retention_min_runs == 3
    assert settings.memory_cleanup_vacuum is False
