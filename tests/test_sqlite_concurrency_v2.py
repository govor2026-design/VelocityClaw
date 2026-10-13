from __future__ import annotations

import multiprocessing
import sqlite3
from pathlib import Path
from types import SimpleNamespace

from velocity_claw.core.queue import RunQueue
from velocity_claw.memory.store import MemoryStore
from velocity_claw.sqlite import SQLITE_BUSY_TIMEOUT_MS, enable_wal, open_database


def _memory_settings(db_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        memory_enabled=True,
        memory_db_path=str(db_path),
        execution_profile="dev",
    )


def _write_rows(db_path: str, prefix: str, count: int) -> None:
    for index in range(count):
        with open_database(db_path) as connection:
            connection.execute(
                "INSERT INTO concurrent_writes (value) VALUES (?)",
                (f"{prefix}-{index}",),
            )


def _database_pragmas(db_path: Path) -> tuple[str, int]:
    with open_database(db_path) as connection:
        journal_mode = str(connection.execute("PRAGMA journal_mode").fetchone()[0])
        busy_timeout = int(connection.execute("PRAGMA busy_timeout").fetchone()[0])
    return journal_mode, busy_timeout


def test_memory_and_queue_databases_enable_wal_and_busy_timeout(tmp_path: Path) -> None:
    memory_path = tmp_path / "memory.db"
    queue_path = tmp_path / "queue.db"

    MemoryStore(_memory_settings(memory_path))
    RunQueue(db_path=str(queue_path))

    assert _database_pragmas(memory_path) == ("wal", SQLITE_BUSY_TIMEOUT_MS)
    assert _database_pragmas(queue_path) == ("wal", SQLITE_BUSY_TIMEOUT_MS)

    with open_database(memory_path) as connection:
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_two_processes_write_shared_wal_database(tmp_path: Path) -> None:
    db_path = tmp_path / "shared.db"
    writes_per_process = 50
    with open_database(db_path) as connection:
        enable_wal(connection)
        connection.execute(
            "CREATE TABLE concurrent_writes (id INTEGER PRIMARY KEY, value TEXT NOT NULL UNIQUE)"
        )

    context = multiprocessing.get_context("spawn")
    processes = [
        context.Process(
            target=_write_rows,
            args=(str(db_path), prefix, writes_per_process),
        )
        for prefix in ("api", "telegram")
    ]
    for process in processes:
        process.start()
    try:
        for process in processes:
            process.join(timeout=20)
            assert process.exitcode == 0
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)

    with sqlite3.connect(db_path) as connection:
        row_count = connection.execute("SELECT COUNT(*) FROM concurrent_writes").fetchone()[0]
    assert row_count == writes_per_process * len(processes)
