from __future__ import annotations

import os
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from velocity_claw.sqlite import SQLITE_BUSY_TIMEOUT_MS, SQLITE_TIMEOUT_SECONDS

DEFAULT_BACKUP_KEEP = 14


def backup_sqlite_database(source_path: str | Path, destination_path: str | Path) -> dict[str, Any]:
    """Create an integrity-checked, atomically published SQLite online backup."""
    source = Path(source_path).expanduser().resolve()
    destination = Path(destination_path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"SQLite database does not exist: {source}")
    if source == destination:
        raise ValueError("Backup destination must differ from the source database")

    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
    source_uri = f"{source.as_uri()}?mode=ro"
    try:
        temporary.touch(mode=0o600, exist_ok=False)
        with closing(
            sqlite3.connect(
                source_uri,
                uri=True,
                timeout=SQLITE_TIMEOUT_SECONDS,
            )
        ) as source_connection:
            source_connection.execute(f"PRAGMA busy_timeout = {SQLITE_BUSY_TIMEOUT_MS}")
            with closing(
                sqlite3.connect(
                    temporary,
                    timeout=SQLITE_TIMEOUT_SECONDS,
                )
            ) as destination_connection:
                source_connection.backup(destination_connection)
                integrity = destination_connection.execute("PRAGMA integrity_check").fetchone()
                if not integrity or str(integrity[0]).lower() != "ok":
                    detail = integrity[0] if integrity else "no result"
                    raise RuntimeError(f"SQLite backup integrity check failed: {detail}")
                destination_connection.commit()
        os.replace(temporary, destination)
        destination.chmod(0o600)
    finally:
        temporary.unlink(missing_ok=True)

    return {
        "source": str(source),
        "path": str(destination),
        "bytes": destination.stat().st_size,
        "integrity_check": "ok",
    }


def _prune_backups(backup_dir: Path, source_name: str, keep: int) -> list[str]:
    prefix = f"{source_name}--"
    candidates = sorted(
        (
            path
            for path in backup_dir.iterdir()
            if path.is_file()
            and path.name.startswith(prefix)
            and path.name.endswith(".sqlite3")
        ),
        key=lambda path: path.name,
        reverse=True,
    )
    pruned: list[str] = []
    for path in candidates[keep:]:
        path.unlink()
        pruned.append(str(path))
    return pruned


def backup_runtime_databases(
    memory_db_path: str | Path,
    backup_dir: str | Path,
    *,
    keep: int = DEFAULT_BACKUP_KEEP,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Back up the memory and queue databases while live services keep running."""
    if keep < 1:
        raise ValueError("Backup retention must be at least 1")

    memory_path = Path(memory_db_path).expanduser().resolve()
    destination_dir = Path(backup_dir).expanduser().resolve()
    destination_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    timestamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    stamp = timestamp.strftime("%Y%m%dT%H%M%S%fZ")

    created: list[dict[str, Any]] = []
    skipped: list[str] = []
    pruned: list[str] = []
    for source in (memory_path, Path(f"{memory_path}.queue")):
        if not source.is_file():
            skipped.append(str(source))
            continue
        destination = destination_dir / f"{source.name}--{stamp}.sqlite3"
        created.append(backup_sqlite_database(source, destination))
        pruned.extend(_prune_backups(destination_dir, source.name, keep))

    return {
        "status": "ok" if created else "no_databases",
        "created_at": timestamp.isoformat(),
        "backup_dir": str(destination_dir),
        "retention": keep,
        "created": created,
        "skipped": skipped,
        "pruned": pruned,
    }
