from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

SQLITE_TIMEOUT_SECONDS = 30.0
SQLITE_BUSY_TIMEOUT_MS = 30_000


@contextmanager
def open_database(db_path: str | Path) -> Iterator[sqlite3.Connection]:
    """Open a consistently configured SQLite connection and always close it."""
    connection = sqlite3.connect(str(db_path), timeout=SQLITE_TIMEOUT_SECONDS)
    try:
        connection.execute(f"PRAGMA busy_timeout = {SQLITE_BUSY_TIMEOUT_MS}")
        connection.execute("PRAGMA foreign_keys = ON")
        with connection:
            yield connection
    finally:
        connection.close()


def enable_wal(connection: sqlite3.Connection) -> None:
    """Enable settings suited to API and Telegram processes sharing one database."""
    row = connection.execute("PRAGMA journal_mode = WAL").fetchone()
    journal_mode = str(row[0]).lower() if row else ""
    if journal_mode != "wal":
        raise RuntimeError(f"Unable to enable SQLite WAL mode: {journal_mode or 'unknown'}")
    connection.execute("PRAGMA synchronous = NORMAL")
