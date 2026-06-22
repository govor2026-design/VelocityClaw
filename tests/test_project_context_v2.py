from pathlib import Path
from types import SimpleNamespace

import pytest

from velocity_claw.core.agent import VelocityClawAgent
from velocity_claw.memory.context_v2 import ProjectContextV2, normalize_tokens, task_similarity
from velocity_claw.memory.store import MemoryStore


class MemorySettings:
    memory_enabled = True
    memory_retention_days = 30
    memory_retention_min_runs = 10
    memory_cleanup_vacuum = False

    def __init__(self, db_path: Path):
        self.memory_db_path = str(db_path)


def build_memory(tmp_path: Path) -> MemoryStore:
    return MemoryStore(MemorySettings(tmp_path / "memory.db"))


def test_task_similarity_matches_reordered_repo_terms():
    score, matched = task_similarity(
        "Fix queue worker cancellation",
        "Repair cancellation handling in queue workers",
    )

    assert score > 0.4
    assert "queue" in matched
    assert "cancellation" in matched
    assert normalize_tokens("Fix the queue") == {"fix", "queue"}


def test_structured_knowledge_lifecycle(tmp_path: Path):
    context = ProjectContextV2(build_memory(tmp_path))

    created = context.remember(
        "tests.command",
        "pytest -q",
        category="test_command",
        source="operator",
        confidence=0.95,
    )
    updated = context.remember(
        "tests.command",
        "pytest -q tests",
        category="test_command",
        source="verified_run",
        confidence=1.0,
    )

    assert created["key"] == "tests.command"
    assert updated["value"] == "pytest -q tests"
    assert updated["source"] == "verified_run"
    assert context.list(category="test_command")[0]["confidence"] == 1.0
    assert context.forget("tests.command") is True
    assert context.get("tests.command") is None

    with pytest.raises(ValueError, match="knowledge_key_invalid"):
        context.remember("bad key", "value")

    with pytest.raises(ValueError, match="knowledge_confidence_out_of_range"):
        context.remember("valid.key", "value", confidence=1.5)


def test_build_separates_reusable_knowledge_from_run_trace(tmp_path: Path):
    memory = build_memory(tmp_path)
    context = ProjectContextV2(memory)
    context.remember("queue.storage", "SQLite", category="architecture", confidence=1.0)
    memory.save_project_note("task", "Fix queue cancellation")
    memory.save_project_note("run_summary", "Temporary run result")
    memory.save_project_note("architecture", "Queue state is persisted in SQLite")
    memory.save_project_note("test_command", "pytest -q tests/test_queue_persistence_v2.py")

    related_id = memory.create_run("Repair cancellation handling in queue workers")
    memory.update_run_status(related_id, "completed")
    unrelated_id = memory.create_run("Update dashboard typography")
    memory.update_run_status(unrelated_id, "completed")

    built = context.build("Fix queue worker cancellation", limit=5)

    assert built["context_version"] == 2
    assert built["reusable_knowledge"][0]["key"] == "queue.storage"
    assert {item["note_type"] for item in built["reusable_notes"]} == {"architecture", "test_command"}
    assert built["planning_signals"]["ignored_trace_notes"] >= 2
    assert built["related_runs"][0]["run_id"] == related_id
    assert all(item["run_id"] != unrelated_id for item in built["related_runs"])
    assert built["planning_signals"]["reuse_prior_success"] is True


def test_context_ingestion_accepts_mapping_and_records_usage(tmp_path: Path):
    context = ProjectContextV2(build_memory(tmp_path))

    remembered = context.ingest_context(
        {
            "project_knowledge": {
                "repo.language": "Python",
                "repo.test_command": "pytest -q",
            }
        }
    )
    built = context.build("Run Python tests", limit=5)

    assert remembered == ["repo.language", "repo.test_command"]
    entries = {item["key"]: item for item in context.list(limit=10)}
    assert entries["repo.language"]["use_count"] >= 1
    assert entries["repo.test_command"]["use_count"] >= 1
    assert built["planning_signals"]["reusable_knowledge_count"] == 2


class FakeMemory:
    def build_planning_context(self):
        return {
            "project_facts": {"legacy": "kept"},
            "recent_notes": [{"note_type": "task", "content": "old trace"}],
            "recent_run_tasks": ["unrelated old run"],
            "recent_failed_tasks": [],
        }

    def list_recent_runs(self, limit=10):
        return []

    def list_pending_approvals(self):
        return []

    def get_last_failed_run(self):
        return None


class FakeProjectContext:
    def ingest_context(self, context):
        return ["repo.path"]

    def build(self, task, limit=5):
        return {
            "context_version": 2,
            "reusable_knowledge": [
                {"key": "repo.path", "value": "velocity_claw/core", "confidence": 1.0}
            ],
            "reusable_notes": [
                {"note_type": "architecture", "content": "Core runtime lives under velocity_claw/core"}
            ],
            "related_runs": [
                {"task": "Fix queue cancellation", "status": "running"},
                {"task": "Fix queue worker lifecycle", "status": "completed"},
                {"task": "Fix queue cancellation", "status": "failed"},
            ],
            "planning_signals": {"reuse_prior_success": True},
        }


def test_agent_projects_v2_context_into_existing_planner_contract():
    agent = VelocityClawAgent.__new__(VelocityClawAgent)
    agent.settings = SimpleNamespace(workspace_root="/repo")
    agent.memory = FakeMemory()
    agent.project_context = FakeProjectContext()

    merged = agent._build_planning_context({}, "Fix queue cancellation")
    planning = merged["planning_context"]

    assert planning["project_facts"]["legacy"] == "kept"
    assert planning["project_facts"]["knowledge.repo.path"] == "velocity_claw/core"
    assert planning["recent_notes"][0]["note_type"] == "architecture"
    assert planning["recent_run_tasks"] == [
        "Fix queue worker lifecycle",
        "Fix queue cancellation",
    ]
    assert planning["recent_failed_tasks"] == ["Fix queue cancellation"]
    assert planning["project_memory_v2"]["related_runs"] == [
        {"task": "Fix queue worker lifecycle", "status": "completed"},
        {"task": "Fix queue cancellation", "status": "failed"},
    ]
    assert planning["memory_signals_v2"]["reuse_prior_success"] is True
    assert planning["knowledge_ingested"] == ["repo.path"]
