from __future__ import annotations

import io
import json
import sqlite3
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from velocity_claw import cli
from velocity_claw.backup import backup_runtime_databases, backup_sqlite_database
from velocity_claw.config.settings import Settings
from velocity_claw.sqlite import enable_wal, open_database


def _create_database(path: Path, value: str) -> None:
    with open_database(path) as connection:
        enable_wal(connection)
        connection.execute("CREATE TABLE records (value TEXT NOT NULL)")
        connection.execute("INSERT INTO records (value) VALUES (?)", (value,))


def _read_value(path: Path) -> str:
    with sqlite3.connect(path) as connection:
        return str(connection.execute("SELECT value FROM records").fetchone()[0])


def test_online_backup_is_complete_and_integrity_checked(tmp_path: Path) -> None:
    source = tmp_path / "memory.db"
    destination = tmp_path / "backups" / "memory.sqlite3"
    _create_database(source, "memory-state")

    result = backup_sqlite_database(source, destination)

    assert result["integrity_check"] == "ok"
    assert result["bytes"] > 0
    assert _read_value(destination) == "memory-state"
    assert destination.stat().st_mode & 0o777 == 0o600
    assert not list(destination.parent.glob("*.tmp"))


def test_failed_backup_is_not_published_and_removes_temporary_file(tmp_path: Path) -> None:
    source = tmp_path / "invalid.db"
    destination = tmp_path / "backups" / "invalid.sqlite3"
    source.write_text("not a sqlite database", encoding="utf-8")

    with pytest.raises(sqlite3.DatabaseError):
        backup_sqlite_database(source, destination)

    assert not destination.exists()
    assert not list(destination.parent.glob(".*.tmp"))


def test_runtime_backup_covers_queue_and_prunes_retention(tmp_path: Path) -> None:
    memory_path = tmp_path / "memory.db"
    queue_path = Path(f"{memory_path}.queue")
    backup_dir = tmp_path / "backups"
    _create_database(memory_path, "memory-state")
    _create_database(queue_path, "queue-state")
    start = datetime(2026, 10, 13, tzinfo=timezone.utc)

    result = None
    for offset in range(3):
        result = backup_runtime_databases(
            memory_path,
            backup_dir,
            keep=2,
            now=start + timedelta(minutes=offset),
        )

    assert result is not None
    assert result["status"] == "ok"
    assert len(result["created"]) == 2
    assert len(result["pruned"]) == 2
    memory_backups = sorted(backup_dir.glob("memory.db--*.sqlite3"))
    queue_backups = sorted(backup_dir.glob("memory.db.queue--*.sqlite3"))
    assert len(memory_backups) == 2
    assert len(queue_backups) == 2
    assert _read_value(memory_backups[-1]) == "memory-state"
    assert _read_value(queue_backups[-1]) == "queue-state"


def test_backup_cli_emits_machine_readable_result(tmp_path: Path) -> None:
    memory_path = tmp_path / "memory.db"
    backup_dir = tmp_path / "backups"
    _create_database(memory_path, "memory-state")
    settings = Settings(memory_db_path=str(memory_path), workspace_root=str(tmp_path))

    output = io.StringIO()
    with (
        patch("velocity_claw.cli.load_settings", return_value=settings),
        redirect_stdout(output),
    ):
        cli.backup_databases_cli(str(backup_dir), keep=3, as_json=True)

    payload = json.loads(output.getvalue())
    assert payload["status"] == "ok"
    assert payload["retention"] == 3
    assert len(payload["created"]) == 1
    assert payload["skipped"] == [f"{memory_path}.queue"]
