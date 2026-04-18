import sqlite3
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from velocity_claw.config.settings import Settings


class MemoryStore:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.enabled = settings.memory_enabled
        self.db_path = settings.memory_db_path
        self._ensure_tables()

    def _ensure_tables(self):
        if not self.enabled:
            return
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY, task TEXT, result TEXT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS preferences (id INTEGER PRIMARY KEY, key TEXT UNIQUE, value TEXT)"
            )

    def save_task_history(self, task: str) -> None:
        if not self.enabled:
            return
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("INSERT INTO history (task, result) VALUES (?, ?)", (task, ""))

    def save_task_result(self, task: str, result: Dict[str, Any]) -> None:
        if not self.enabled:
            return
        payload = json.dumps(result, ensure_ascii=False)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE history SET result = ? WHERE task = ? ORDER BY id DESC LIMIT 1", (payload, task))

    def load_recent_context(self, limit: int = 5) -> List[Dict[str, Any]]:
        if not self.enabled:
            return []
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("SELECT task, result, created_at FROM history ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
            return [
                {"task": row[0], "result": json.loads(row[1]) if row[1] else {}, "created_at": row[2]}
                for row in rows
            ]

    def save_preference(self, key: str, value: Any) -> None:
        if not self.enabled:
            return
        payload = json.dumps(value, ensure_ascii=False)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO preferences (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, payload),
            )

    def load_preference(self, key: str) -> Optional[Any]:
        if not self.enabled:
            return None
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT value FROM preferences WHERE key = ?", (key,)).fetchone()
            return json.loads(row[0]) if row else None

    def clear_short_term(self) -> None:
        if not self.enabled:
            return
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM history WHERE id > 0")

