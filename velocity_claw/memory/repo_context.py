from __future__ import annotations

from collections import Counter
from typing import Any

from velocity_claw.memory.relevance import compact_run, similarity, tokenize


REUSABLE_NOTE_TYPES = {
    "architecture",
    "constraint",
    "decision",
    "dependency",
    "convention",
    "repository",
    "project",
    "knowledge",
}

TRACE_NOTE_TYPES = {
    "task",
    "plan_summary",
    "run_summary",
    "run_error",
    "approval_pause",
    "auto_fix",
}


class RepoKnowledgeIndex:
    def __init__(self, memory: Any):
        self.memory = memory

    def reusable_notes(self, limit: int = 10) -> list[dict[str, Any]]:
        notes = []
        seen: set[tuple[str, str]] = set()
        for note in self.memory.load_recent_project_notes(limit=max(limit * 5, 20)):
            note_type = str(note.get("note_type") or "").strip().lower()
            content = str(note.get("content") or "").strip()
            if not content or note_type in TRACE_NOTE_TYPES:
                continue
            if note_type not in REUSABLE_NOTE_TYPES and not note_type.startswith("knowledge:"):
                continue
            key = (note_type, content.lower())
            if key in seen:
                continue
            seen.add(key)
            notes.append(note)
            if len(notes) >= limit:
                break
        return notes

    def trace_notes(self, limit: int = 10) -> list[dict[str, Any]]:
        return [
            note
            for note in self.memory.load_recent_project_notes(limit=max(limit * 3, 20))
            if str(note.get("note_type") or "").strip().lower() in TRACE_NOTE_TYPES
        ][:limit]

    def related_runs(self, task: str, limit: int = 5, min_score: float = 0.18) -> list[dict[str, Any]]:
        ranked: list[tuple[float, dict[str, Any]]] = []
        for summary in self.memory.list_recent_runs(limit=100):
            score = similarity(task, summary.get("task") or "")
            if score < min_score:
                continue
            full = self.memory.load_run(summary["run_id"]) or summary
            ranked.append((score, compact_run(full, score=score)))
        ranked.sort(key=lambda item: (item[0], item[1].get("created_at") or ""), reverse=True)
        return [payload for _, payload in ranked[:limit]]

    def recurring_signals(self, limit: int = 50) -> dict[str, Any]:
        status_counts: Counter[str] = Counter()
        topic_counts: Counter[str] = Counter()
        failed_topics: Counter[str] = Counter()
        for run in self.memory.list_recent_runs(limit=limit):
            status = str(run.get("status") or "unknown")
            status_counts[status] += 1
            topics = tokenize(run.get("task") or "")
            topic_counts.update(topics)
            if status == "failed":
                failed_topics.update(topics)
        return {
            "run_status_counts": dict(status_counts),
            "recurring_topics": [token for token, count in topic_counts.most_common(8) if count > 1],
            "recurring_failure_topics": [token for token, count in failed_topics.most_common(8) if count > 1],
        }

    def build_project_knowledge(self, limit: int = 10) -> dict[str, Any]:
        facts = self.memory.list_project_facts()
        notes = self.reusable_notes(limit=limit)
        return {
            "facts": facts,
            "reusable_notes": notes,
            "signals": self.recurring_signals(),
            "counts": {"facts": len(facts), "reusable_notes": len(notes)},
        }

    def build_planning_context(self, task: str, limit: int = 5) -> dict[str, Any]:
        knowledge = self.build_project_knowledge(limit=max(limit, 5))
        related = self.related_runs(task, limit=limit)
        return {
            "project_knowledge": knowledge,
            "related_runs": related,
            "related_failed_runs": [run for run in related if run.get("status") == "failed"],
            "avoid_rediscovery": bool(knowledge["facts"] or knowledge["reusable_notes"] or related),
        }

    def build_resume_context(self, task: str, limit: int = 5) -> dict[str, Any]:
        related = self.related_runs(task, limit=limit)
        return {
            "task": task,
            "project_knowledge": self.build_project_knowledge(limit=max(limit, 5)),
            "related_runs": related,
            "related_failed_runs": [run for run in related if run.get("status") == "failed"],
            "recent_trace": self.trace_notes(limit=limit),
            "reuse_hint": "Reuse saved facts, decisions, constraints, and successful prior findings before repeating repository inspection.",
        }


def install_repo_aware_memory_v2(memory_cls: type) -> None:
    if getattr(memory_cls, "_repo_aware_v2_installed", False):
        return

    original_repo_summary = memory_cls.build_repo_context_summary
    original_planning = memory_cls.build_planning_context
    original_resume = memory_cls.build_resume_context

    def build_repo_context_summary(self, limit: int = 5):
        payload = original_repo_summary(self, limit=limit)
        payload["project_knowledge_v2"] = RepoKnowledgeIndex(self).build_project_knowledge(limit=max(limit, 5))
        payload["memory_model"] = "repo-aware-v2"
        return payload

    def build_planning_context(self, limit: int = 5, task: str | None = None):
        payload = original_planning(self, limit=limit)
        if task:
            payload.update(RepoKnowledgeIndex(self).build_planning_context(task, limit=limit))
        else:
            payload["project_knowledge"] = RepoKnowledgeIndex(self).build_project_knowledge(limit=max(limit, 5))
            payload["avoid_rediscovery"] = bool(payload["project_knowledge"]["facts"] or payload["project_knowledge"]["reusable_notes"])
        payload["memory_model"] = "repo-aware-v2"
        return payload

    def build_resume_context(self, task: str, limit: int = 5):
        payload = original_resume(self, task, limit=limit)
        payload.update(RepoKnowledgeIndex(self).build_resume_context(task, limit=limit))
        payload["memory_model"] = "repo-aware-v2"
        return payload

    def save_reusable_knowledge(self, knowledge_type: str, content: str):
        note_type = str(knowledge_type or "knowledge").strip().lower()
        if note_type not in REUSABLE_NOTE_TYPES and not note_type.startswith("knowledge:"):
            note_type = f"knowledge:{note_type}"
        self.save_project_note(note_type, str(content).strip())

    memory_cls.build_repo_context_summary = build_repo_context_summary
    memory_cls.build_planning_context = build_planning_context
    memory_cls.build_resume_context = build_resume_context
    memory_cls.save_reusable_knowledge = save_reusable_knowledge
    memory_cls._repo_aware_v2_installed = True
