from __future__ import annotations

import json
import math
import re
import sqlite3
from collections import Counter
from datetime import datetime
from typing import Any, Iterable


TRACE_NOTE_TYPES = {
    "task",
    "plan_summary",
    "run_summary",
    "run_error",
    "approval_pause",
    "approval_decision",
    "auto_fix",
    "resume_failure",
    "resume_complete",
}

REUSABLE_NOTE_TYPES = {
    "architecture",
    "command",
    "constraint",
    "convention",
    "decision",
    "dependency",
    "path",
    "project_fact",
    "test_command",
}

STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in", "is", "it",
    "of", "on", "or", "that", "the", "this", "to", "with",
    "а", "без", "в", "во", "для", "до", "и", "из", "или", "к", "как", "на", "не", "но",
    "о", "по", "при", "с", "со", "что", "это",
}

TOKEN_RE = re.compile(r"[a-zA-Zа-яА-ЯёЁ0-9_./:-]+")
ACTIVE_RUN_STATUSES = {"running", "resuming_after_approval"}


def _now() -> str:
    return datetime.now().isoformat()


def _safe_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _normalize_token(token: str) -> str:
    """Normalize simple English morphology without touching paths or identifiers."""
    if not token.isascii() or not token.isalpha():
        return token
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 4 and token.endswith("s") and not token.endswith(("ss", "us", "is")):
        return token[:-1]
    return token


def normalize_tokens(value: str | None) -> set[str]:
    if not value:
        return set()
    tokens: set[str] = set()
    for raw in TOKEN_RE.findall(value.lower()):
        token = _normalize_token(raw.strip("./:-_"))
        if len(token) < 2 or token in STOP_WORDS:
            continue
        tokens.add(token)
    return tokens


def task_similarity(query: str, candidate: str) -> tuple[float, list[str]]:
    query_tokens = normalize_tokens(query)
    candidate_tokens = normalize_tokens(candidate)
    if not query_tokens or not candidate_tokens:
        return 0.0, []
    common = query_tokens & candidate_tokens
    if not common:
        return 0.0, []
    recall = len(common) / len(query_tokens)
    precision = len(common) / len(candidate_tokens)
    score = (2 * precision * recall) / (precision + recall)
    query_lower = query.strip().lower()
    candidate_lower = candidate.strip().lower()
    if query_lower and (query_lower in candidate_lower or candidate_lower in query_lower):
        score = min(1.0, score + 0.2)
    return round(score, 4), sorted(common)


class ProjectContextV2:
    """Structured reusable project knowledge plus task-aware run retrieval."""

    def __init__(self, memory: Any):
        self.memory = memory
        self.enabled = bool(getattr(memory, "enabled", False))
        self.db_path = getattr(memory, "db_path", None)
        self._ensure_table()

    def _ensure_table(self) -> None:
        if not self.enabled or not self.db_path:
            return
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS project_knowledge (
                    key TEXT PRIMARY KEY,
                    category TEXT NOT NULL,
                    value TEXT NOT NULL,
                    source TEXT NOT NULL,
                    confidence REAL NOT NULL DEFAULT 1.0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_used_at TEXT,
                    use_count INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_project_knowledge_category "
                "ON project_knowledge(category, updated_at)"
            )

    def remember(
        self,
        key: str,
        value: Any,
        *,
        category: str = "fact",
        source: str = "operator",
        confidence: float = 1.0,
    ) -> dict[str, Any]:
        if not self.enabled:
            return {"status": "disabled", "key": key}
        normalized_key = str(key or "").strip()
        normalized_category = str(category or "fact").strip().lower()
        normalized_source = str(source or "operator").strip().lower()
        if not normalized_key:
            raise ValueError("knowledge_key_required")
        if len(normalized_key) > 160:
            raise ValueError("knowledge_key_too_long")
        if not re.fullmatch(r"[a-zA-Z0-9_.:/-]+", normalized_key):
            raise ValueError("knowledge_key_invalid")
        if not re.fullmatch(r"[a-z0-9_.-]+", normalized_category):
            raise ValueError("knowledge_category_invalid")
        confidence_value = float(confidence)
        if not 0.0 <= confidence_value <= 1.0:
            raise ValueError("knowledge_confidence_out_of_range")
        payload = _safe_json(value)
        timestamp = _now()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO project_knowledge (
                    key, category, value, source, confidence, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    category = excluded.category,
                    value = excluded.value,
                    source = excluded.source,
                    confidence = excluded.confidence,
                    updated_at = excluded.updated_at
                """,
                (
                    normalized_key,
                    normalized_category,
                    payload,
                    normalized_source,
                    confidence_value,
                    timestamp,
                    timestamp,
                ),
            )
        return self.get(normalized_key) or {"key": normalized_key}

    def forget(self, key: str) -> bool:
        if not self.enabled:
            return False
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM project_knowledge WHERE key = ?", (key,))
        return bool(cursor.rowcount)

    def get(self, key: str) -> dict[str, Any] | None:
        if not self.enabled:
            return None
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT key, category, value, source, confidence,
                       created_at, updated_at, last_used_at, use_count
                FROM project_knowledge WHERE key = ?
                """,
                (key,),
            ).fetchone()
        return self._row_to_entry(row) if row else None

    def list(self, *, limit: int = 50, category: str | None = None) -> list[dict[str, Any]]:
        if not self.enabled:
            return []
        bounded_limit = max(1, min(int(limit), 200))
        with sqlite3.connect(self.db_path) as conn:
            if category:
                rows = conn.execute(
                    """
                    SELECT key, category, value, source, confidence,
                           created_at, updated_at, last_used_at, use_count
                    FROM project_knowledge
                    WHERE category = ?
                    ORDER BY confidence DESC, updated_at DESC, key
                    LIMIT ?
                    """,
                    (category, bounded_limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT key, category, value, source, confidence,
                           created_at, updated_at, last_used_at, use_count
                    FROM project_knowledge
                    ORDER BY confidence DESC, updated_at DESC, key
                    LIMIT ?
                    """,
                    (bounded_limit,),
                ).fetchall()
        return [self._row_to_entry(row) for row in rows]

    def _all_entries(self) -> list[dict[str, Any]]:
        """Load every candidate before task-relevance scoring."""
        if not self.enabled:
            return []
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT key, category, value, source, confidence,
                       created_at, updated_at, last_used_at, use_count
                FROM project_knowledge
                """
            ).fetchall()
        return [self._row_to_entry(row) for row in rows]

    def _row_to_entry(self, row: Iterable[Any]) -> dict[str, Any]:
        values = list(row)
        try:
            decoded = json.loads(values[2])
        except (TypeError, ValueError):
            decoded = values[2]
        return {
            "key": values[0],
            "category": values[1],
            "value": decoded,
            "source": values[3],
            "confidence": values[4],
            "created_at": values[5],
            "updated_at": values[6],
            "last_used_at": values[7],
            "use_count": values[8],
        }

    def ingest_context(self, context: dict[str, Any] | None) -> list[str]:
        payload = (context or {}).get("project_knowledge")
        if not payload:
            return []
        if isinstance(payload, dict) and "key" in payload:
            items = [payload]
        elif isinstance(payload, dict):
            items = [
                {"key": key, "value": value, "category": "fact", "source": "task_context"}
                for key, value in payload.items()
            ]
        elif isinstance(payload, list):
            items = [item for item in payload if isinstance(item, dict)]
        else:
            raise ValueError("project_knowledge_must_be_object_or_list")

        remembered: list[str] = []
        for item in items[:50]:
            entry = self.remember(
                item.get("key", ""),
                item.get("value"),
                category=item.get("category", "fact"),
                source=item.get("source", "task_context"),
                confidence=item.get("confidence", 1.0),
            )
            if entry.get("key"):
                remembered.append(entry["key"])
        return remembered

    def _mark_used(self, keys: list[str]) -> None:
        if not keys or not self.enabled:
            return
        placeholders = ",".join("?" for _ in keys)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                f"""
                UPDATE project_knowledge
                SET last_used_at = ?, use_count = use_count + 1
                WHERE key IN ({placeholders})
                """,
                (_now(), *keys),
            )

    def _reusable_notes(self, limit: int) -> tuple[list[dict[str, Any]], int]:
        notes = self.memory.load_recent_project_notes(limit=max(50, limit * 10))
        reusable: list[dict[str, Any]] = []
        ignored_trace = 0
        seen: set[tuple[str, str]] = set()
        for note in notes:
            note_type = str(note.get("note_type") or "").strip().lower()
            content = str(note.get("content") or "").strip()
            if note_type in TRACE_NOTE_TYPES or note_type not in REUSABLE_NOTE_TYPES:
                ignored_trace += 1
                continue
            if not content:
                continue
            identity = (note_type, content.lower())
            if identity in seen:
                continue
            seen.add(identity)
            reusable.append(note)
            if len(reusable) >= limit:
                break
        return reusable, ignored_trace

    def _related_runs(self, task: str, limit: int) -> list[dict[str, Any]]:
        ranked: list[tuple[float, dict[str, Any], list[str]]] = []
        for run in self.memory.list_recent_runs(limit=100):
            if run.get("status") in ACTIVE_RUN_STATUSES:
                continue
            score, matched = task_similarity(task, run.get("task") or "")
            if score > 0:
                ranked.append((score, run, matched))
        ranked.sort(key=lambda item: (item[0], item[1].get("created_at") or ""), reverse=True)

        related: list[dict[str, Any]] = []
        for score, run, matched in ranked[:limit]:
            loaded = self.memory.load_run(run["run_id"])
            report = (loaded or {}).get("report") or {}
            forensics = (loaded or {}).get("forensics") or {}
            related.append(
                {
                    **run,
                    "similarity": score,
                    "matched_terms": matched,
                    "executive_summary": report.get("executive_summary"),
                    "failed_step": forensics.get("failed_step"),
                    "last_step": forensics.get("last_step"),
                    "artifact_counts": forensics.get("artifact_counts_by_type", {}),
                }
            )
        return related

    def _knowledge_relevance(self, task: str, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        task_tokens = normalize_tokens(task)
        ranked: list[tuple[float, dict[str, Any]]] = []
        for entry in entries:
            entry_tokens = normalize_tokens(
                f"{entry.get('key')} {entry.get('category')} {_safe_json(entry.get('value'))}"
            )
            common = task_tokens & entry_tokens
            lexical = len(common) / max(1, len(task_tokens))
            confidence = float(entry.get("confidence") or 0.0)
            usage_bonus = min(0.1, math.log1p(int(entry.get("use_count") or 0)) / 30)
            score = round((lexical * 0.7) + (confidence * 0.25) + usage_bonus, 4)
            ranked.append((score, {**entry, "relevance": score, "matched_terms": sorted(common)}))
        ranked.sort(key=lambda item: (item[0], item[1].get("updated_at") or ""), reverse=True)
        return [entry for _, entry in ranked]

    def build(self, task: str, *, limit: int = 5) -> dict[str, Any]:
        bounded_limit = max(1, min(int(limit), 20))
        structured = self._knowledge_relevance(task, self._all_entries())[:bounded_limit]
        self._mark_used([entry["key"] for entry in structured])
        reusable_notes, ignored_trace = self._reusable_notes(bounded_limit)
        related_runs = self._related_runs(task, bounded_limit) if task.strip() else []
        failures = [run for run in related_runs if run.get("status") == "failed"]
        successes = [run for run in related_runs if run.get("status") == "completed"]
        repeated_failure_tools = Counter(
            (run.get("failed_step") or {}).get("tool")
            for run in failures
            if (run.get("failed_step") or {}).get("tool")
        )
        return {
            "context_version": 2,
            "task": task,
            "reusable_knowledge": structured,
            "legacy_project_facts": self.memory.list_project_facts(),
            "reusable_notes": reusable_notes,
            "related_runs": related_runs,
            "prior_successes": successes,
            "prior_failures": failures,
            "planning_signals": {
                "related_run_count": len(related_runs),
                "reusable_knowledge_count": len(structured),
                "reusable_note_count": len(reusable_notes),
                "ignored_trace_notes": ignored_trace,
                "repeated_failure_tools": [
                    {"tool": tool, "count": count}
                    for tool, count in repeated_failure_tools.most_common(5)
                ],
                "inspect_before_edit": bool(failures),
                "reuse_prior_success": bool(successes),
            },
            "trace": {
                "recent_runs": self.memory.list_recent_runs(limit=bounded_limit),
                "recent_notes": self.memory.load_recent_project_notes(limit=bounded_limit),
            },
        }
