import sqlite3
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
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
            conn.execute("""
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    task TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    completed_at DATETIME
                )
            """)
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
            conn.execute("""
                CREATE TABLE IF NOT EXISTS preferences (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS artifacts (
                    id INTEGER PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    step_id INTEGER,
                    name TEXT NOT NULL,
                    artifact_type TEXT DEFAULT 'text',
                    content TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (run_id) REFERENCES runs (run_id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS project_facts (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS project_notes (
                    id INTEGER PRIMARY KEY,
                    note_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS fix_attempts (
                    id INTEGER PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    attempt_no INTEGER NOT NULL,
                    summary TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (run_id) REFERENCES runs (run_id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS approval_history (
                    id INTEGER PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    step_id INTEGER NOT NULL,
                    decision TEXT NOT NULL,
                    actor TEXT,
                    reason TEXT,
                    payload TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (run_id) REFERENCES runs (run_id)
                )
            """)

    def create_run(self, task: str) -> str:
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
                json.dumps(step.get("result"), ensure_ascii=False),
                step.get("error"),
                step.get("started_at"),
                step.get("completed_at"),
            ))

    def update_run_status(self, run_id: str, status: str) -> None:
        if not self.enabled:
            return
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE runs SET status = ?, completed_at = ? WHERE run_id = ?",
                (status, datetime.now().isoformat() if status in ["completed", "failed", "rejected"] else None, run_id)
            )

    def load_run(self, run_id: str) -> Optional[Dict]:
        if not self.enabled:
            return None
        with sqlite3.connect(self.db_path) as conn:
            run_row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
            if not run_row:
                return None
            return {
                "run_id": run_row[0],
                "task": run_row[1],
                "status": run_row[2],
                "created_at": run_row[3],
                "completed_at": run_row[4],
                "steps": self.load_steps(run_id),
                "artifacts": self.load_artifacts(run_id),
                "fix_attempts": self.load_fix_attempts(run_id),
                "approval_history": self.load_approval_history(run_id),
            }

    def load_steps(self, run_id: str):
        if not self.enabled:
            return []
        with sqlite3.connect(self.db_path) as conn:
            steps = conn.execute(
                "SELECT step_id, title, tool, args, status, result, error, started_at, completed_at FROM steps WHERE run_id = ? ORDER BY step_id, id",
                (run_id,)
            ).fetchall()
        return [
            {
                "id": s[0],
                "title": s[1],
                "tool": s[2],
                "args": json.loads(s[3]) if s[3] else {},
                "status": s[4],
                "result": json.loads(s[5]) if s[5] is not None else None,
                "error": s[6],
                "started_at": s[7],
                "completed_at": s[8],
            }
            for s in steps
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

    def save_artifact(self, run_id: str, name: str, content: str, step_id: int | None = None, artifact_type: str = "text") -> None:
        if not self.enabled:
            return
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO artifacts (run_id, step_id, name, artifact_type, content) VALUES (?, ?, ?, ?, ?)",
                (run_id, step_id, name, artifact_type, content)
            )

    def load_artifacts(self, run_id: str):
        if not self.enabled:
            return []
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT step_id, name, artifact_type, content, created_at FROM artifacts WHERE run_id = ? ORDER BY id",
                (run_id,),
            ).fetchall()
        return [
            {"step_id": r[0], "name": r[1], "artifact_type": r[2], "content": r[3], "created_at": r[4]}
            for r in rows
        ]

    def save_project_fact(self, key: str, value: Any) -> None:
        if not self.enabled:
            return
        payload = json.dumps(value, ensure_ascii=False)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO project_facts (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP",
                (key, payload),
            )

    def load_project_fact(self, key: str) -> Optional[Any]:
        if not self.enabled:
            return None
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT value FROM project_facts WHERE key = ?", (key,)).fetchone()
            return json.loads(row[0]) if row else None

    def list_project_facts(self) -> dict:
        if not self.enabled:
            return {}
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("SELECT key, value FROM project_facts ORDER BY key").fetchall()
        return {key: json.loads(value) for key, value in rows}

    def save_project_note(self, note_type: str, content: str) -> None:
        if not self.enabled:
            return
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO project_notes (note_type, content) VALUES (?, ?)",
                (note_type, content),
            )

    def load_recent_project_notes(self, limit: int = 10) -> list[dict]:
        if not self.enabled:
            return []
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT note_type, content, created_at FROM project_notes ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {"note_type": row[0], "content": row[1], "created_at": row[2]}
            for row in rows
        ]

    def build_repo_context_summary(self, limit: int = 5) -> dict:
        return {
            "project_facts": self.list_project_facts(),
            "recent_notes": self.load_recent_project_notes(limit=limit),
            "recent_runs": self.list_recent_runs(limit=limit),
            "last_failed_run": self.get_last_failed_run(),
            "recent_fix_attempts": self.list_recent_fix_attempts(limit=limit),
        }

    def build_planning_context(self, limit: int = 5) -> dict:
        recent_notes = self.load_recent_project_notes(limit=limit)
        recent_runs = self.list_recent_runs(limit=limit)
        last_failed = self.get_last_failed_run()
        return {
            "project_facts": self.list_project_facts(),
            "recent_notes": recent_notes,
            "recent_run_tasks": [item["task"] for item in recent_runs],
            "recent_failed_tasks": [item["task"] for item in recent_runs if item["status"] == "failed"],
            "last_failed_run": {
                "task": last_failed["task"],
                "status": last_failed["status"],
            } if last_failed else None,
            "recent_fix_attempts": self.list_recent_fix_attempts(limit=limit),
        }

    def build_resume_context(self, task: str, limit: int = 5) -> dict:
        recent_runs = self.list_recent_runs(limit=20)
        related_runs = [item for item in recent_runs if task.lower() in item["task"].lower()][:limit]
        related_failed = [item for item in related_runs if item["status"] == "failed"]
        last_failed = self.get_last_failed_run()
        return {
            "task": task,
            "related_runs": related_runs,
            "related_failed_runs": related_failed,
            "last_failed_run": {
                "run_id": last_failed["run_id"],
                "task": last_failed["task"],
                "status": last_failed["status"],
            } if last_failed else None,
            "recent_fix_attempts": self.list_recent_fix_attempts(limit=limit),
            "recent_notes": self.load_recent_project_notes(limit=limit),
        }

    def save_fix_attempt(self, run_id: str, attempt_no: int, summary: Any) -> None:
        if not self.enabled:
            return
        payload = json.dumps(summary, ensure_ascii=False)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO fix_attempts (run_id, attempt_no, summary) VALUES (?, ?, ?)",
                (run_id, attempt_no, payload),
            )

    def load_fix_attempts(self, run_id: str):
        if not self.enabled:
            return []
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT attempt_no, summary, created_at FROM fix_attempts WHERE run_id = ? ORDER BY attempt_no",
                (run_id,),
            ).fetchall()
        return [
            {"attempt_no": r[0], "summary": json.loads(r[1]) if r[1] else None, "created_at": r[2]}
            for r in rows
        ]

    def list_recent_fix_attempts(self, limit: int = 10):
        if not self.enabled:
            return []
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT run_id, attempt_no, summary, created_at FROM fix_attempts ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "run_id": r[0],
                "attempt_no": r[1],
                "summary": json.loads(r[2]) if r[2] else None,
                "created_at": r[3],
            }
            for r in rows
        ]

    def save_approval_decision(self, run_id: str, step_id: int, decision: str, actor: str | None = None, reason: str | None = None, payload: Any = None) -> None:
        if not self.enabled:
            return
        encoded = json.dumps(payload, ensure_ascii=False) if payload is not None else None
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO approval_history (run_id, step_id, decision, actor, reason, payload) VALUES (?, ?, ?, ?, ?, ?)",
                (run_id, step_id, decision, actor, reason, encoded),
            )

    def load_approval_history(self, run_id: str):
        if not self.enabled:
            return []
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT step_id, decision, actor, reason, payload, created_at FROM approval_history WHERE run_id = ? ORDER BY id",
                (run_id,),
            ).fetchall()
        return [
            {
                "step_id": r[0],
                "decision": r[1],
                "actor": r[2],
                "reason": r[3],
                "payload": json.loads(r[4]) if r[4] else None,
                "created_at": r[5],
            }
            for r in rows
        ]

    def get_last_failed_run(self) -> Optional[Dict]:
        if not self.enabled:
            return None
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT run_id FROM runs WHERE status = 'failed' ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
        return self.load_run(row[0]) if row else None

    def clear_short_term(self) -> None:
        if not self.enabled:
            return
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                DELETE FROM runs WHERE run_id NOT IN (
                    SELECT run_id FROM runs ORDER BY created_at DESC LIMIT 10
                )
            """)
            conn.execute("DELETE FROM steps WHERE run_id NOT IN (SELECT run_id FROM runs)")
            conn.execute("DELETE FROM artifacts WHERE run_id NOT IN (SELECT run_id FROM runs)")
            conn.execute("DELETE FROM approval_history WHERE run_id NOT IN (SELECT run_id FROM runs)")

    def list_recent_runs(self, limit: int = 20):
        if not self.enabled:
            return []
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT run_id, task, status, created_at, completed_at FROM runs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {"run_id": r[0], "task": r[1], "status": r[2], "created_at": r[3], "completed_at": r[4]}
            for r in rows
        ]

    def list_pending_approvals(self):
        if not self.enabled:
            return []
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT run_id, step_id, title, tool, args, result, started_at, completed_at FROM steps WHERE status = 'pending_approval' ORDER BY started_at DESC"
            ).fetchall()
        approvals = []
        for r in rows:
            approvals.append({
                "run_id": r[0],
                "step_id": r[1],
                "title": r[2],
                "tool": r[3],
                "args": json.loads(r[4]) if r[4] else {},
                "result": json.loads(r[5]) if r[5] else None,
                "started_at": r[6],
                "completed_at": r[7],
            })
        return approvals

    def update_step_status(self, run_id: str, step_id: int, status: str, result: Any = None, error: str | None = None) -> None:
        if not self.enabled:
            return
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE steps SET status = ?, result = ?, error = ?, completed_at = ? WHERE run_id = ? AND step_id = ?",
                (status, json.dumps(result, ensure_ascii=False) if result is not None else None, error, datetime.now().isoformat(), run_id, step_id),
            )
