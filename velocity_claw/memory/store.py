import sqlite3
import json
import uuid
from datetime import datetime
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
            # Runs table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    task TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    completed_at DATETIME
                )
            """)
            # Steps table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS steps (
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
                    completed_at DATETIME,
                    FOREIGN KEY (run_id) REFERENCES runs (run_id)
                )
            """)
            # Preferences table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS preferences (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Artifacts table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS artifacts (
                    id INTEGER PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (run_id) REFERENCES runs (run_id)
                )
            """)

    def create_run(self, task: str) -> str:
        """Create a new run and return run_id."""
        if not self.enabled:
            return str(uuid.uuid4())
        run_id = str(uuid.uuid4())
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO runs (run_id, task, status) VALUES (?, ?, ?)",
                (run_id, task, "running")
            )
        return run_id

    def save_step(self, run_id: str, step: Dict) -> None:
        """Save step execution details."""
        if not self.enabled:
            return
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO steps (run_id, step_id, title, tool, args, status, result, error, started_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                run_id,
                step.get("id"),
                step.get("title"),
                step.get("tool"),
                json.dumps(step.get("args", {}), ensure_ascii=False),
                step.get("status"),
                json.dumps(step.get("result"), ensure_ascii=False) if step.get("result") else None,
                step.get("error"),
                step.get("started_at"),
                step.get("completed_at")
            ))

    def update_run_status(self, run_id: str, status: str) -> None:
        """Update run status."""
        if not self.enabled:
            return
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE runs SET status = ?, completed_at = ? WHERE run_id = ?",
                (status, datetime.now().isoformat() if status in ["completed", "failed"] else None, run_id)
            )

    def load_run(self, run_id: str) -> Optional[Dict]:
        """Load run details."""
        if not self.enabled:
            return None
        with sqlite3.connect(self.db_path) as conn:
            run_row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
            if not run_row:
                return None
            steps = conn.execute("SELECT * FROM steps WHERE run_id = ? ORDER BY step_id", (run_id,)).fetchall()
            return {
                "run_id": run_row[0],
                "task": run_row[1],
                "status": run_row[2],
                "created_at": run_row[3],
                "completed_at": run_row[4],
                "steps": [
                    {
                        "id": s[2],
                        "title": s[3],
                        "tool": s[4],
                        "args": json.loads(s[5]) if s[5] else {},
                        "status": s[6],
                        "result": json.loads(s[7]) if s[7] else None,
                        "error": s[8],
                        "started_at": s[9],
                        "completed_at": s[10]
                    } for s in steps
                ]
            }

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

    def save_artifact(self, run_id: str, name: str, content: str) -> None:
        """Save artifact for run."""
        if not self.enabled:
            return
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO artifacts (run_id, name, content) VALUES (?, ?, ?)",
                (run_id, name, content)
            )

    def clear_short_term(self) -> None:
        """Clear recent runs and steps, keep preferences."""
        if not self.enabled:
            return
        with sqlite3.connect(self.db_path) as conn:
            # Keep only last 10 runs
            conn.execute("""
                DELETE FROM runs WHERE run_id NOT IN (
                    SELECT run_id FROM runs ORDER BY created_at DESC LIMIT 10
                )
            """)
            # Clean up orphaned steps and artifacts
            conn.execute("DELETE FROM steps WHERE run_id NOT IN (SELECT run_id FROM runs)")
            conn.execute("DELETE FROM artifacts WHERE run_id NOT IN (SELECT run_id FROM runs)")

