from pathlib import Path

from velocity_claw.config.settings import Settings
from velocity_claw.memory import MemoryStore
from velocity_claw.memory.relevance import similarity, tokenize
from velocity_claw.planner.planner import Planner


class DummyRouter:
    async def route(self, task_type, prompt):
        return {"text": '{"task":"x","steps":[]}'}


def make_memory(tmp_path: Path, monkeypatch) -> MemoryStore:
    monkeypatch.setenv("VELOCITY_CLAW_ENV", "test")
    monkeypatch.setenv("VELOCITY_CLAW_MEMORY_DB_PATH", str(tmp_path / "memory.db"))
    return MemoryStore(Settings())


def test_similarity_matches_related_tasks_without_full_substring():
    score = similarity(
        "Improve queue worker cancellation and concurrency",
        "Fix concurrency limits for cancelled queue workers",
    )

    assert score >= 0.5
    assert "concurrency" in tokenize("Concurrency controls")
    assert similarity("queue worker", "telegram authorization") == 0.0


def test_reusable_knowledge_is_separated_from_run_trace(tmp_path: Path, monkeypatch):
    memory = make_memory(tmp_path, monkeypatch)
    memory.save_project_fact("package_manager", "pip")
    memory.save_project_note("task", "Inspect package manager")
    memory.save_project_note("run_summary", "Run completed")
    memory.save_reusable_knowledge("architecture", "FastAPI production wrapper installs API hardening")
    memory.save_reusable_knowledge("constraint", "Shell execution stays disabled by default")
    memory.save_reusable_knowledge("architecture", "FastAPI production wrapper installs API hardening")

    context = memory.build_repo_context_summary(limit=10)
    knowledge = context["project_knowledge_v2"]

    assert context["memory_model"] == "repo-aware-v2"
    assert knowledge["facts"]["package_manager"] == "pip"
    assert [item["note_type"] for item in knowledge["reusable_notes"]] == ["constraint", "architecture"]
    assert len(knowledge["reusable_notes"]) == 2
    assert all(item["note_type"] not in {"task", "run_summary"} for item in knowledge["reusable_notes"])


def test_related_runs_are_ranked_and_current_running_run_is_excluded(tmp_path: Path, monkeypatch):
    memory = make_memory(tmp_path, monkeypatch)

    related = memory.create_run("Fix queue cancellation and worker concurrency")
    memory.update_run_status(related, "completed")

    failed = memory.create_run("Queue worker concurrency regression")
    memory.update_run_status(failed, "failed")

    unrelated = memory.create_run("Update Telegram welcome message")
    memory.update_run_status(unrelated, "completed")

    current = memory.create_run("Improve queue worker cancellation")
    memory.save_project_fact("last_task", "Improve queue worker cancellation")

    planning = memory.build_planning_context(limit=5)
    ranked_ids = [item["run_id"] for item in planning["related_runs"]]

    assert planning["memory_model"] == "repo-aware-v2"
    assert planning["avoid_rediscovery"] is True
    assert current not in ranked_ids
    assert unrelated not in ranked_ids
    assert ranked_ids[0] in {related, failed}
    assert failed in [item["run_id"] for item in planning["related_failed_runs"]]


def test_resume_context_replaces_literal_matching_with_ranked_related_runs(tmp_path: Path, monkeypatch):
    memory = make_memory(tmp_path, monkeypatch)
    run_id = memory.create_run("Repair dependency audit release workflow")
    memory.update_run_status(run_id, "completed")
    memory.save_reusable_knowledge("decision", "Release validation runs before tag creation")

    context = memory.build_resume_context("Fix release workflow dependency audit")

    assert context["memory_model"] == "repo-aware-v2"
    assert context["related_runs"][0]["run_id"] == run_id
    assert context["related_runs"][0]["similarity"] > 0
    assert context["project_knowledge"]["reusable_notes"][0]["note_type"] == "decision"
    assert "Reuse saved facts" in context["reuse_hint"]


def test_planner_prompt_includes_repo_aware_signals():
    planner = Planner(DummyRouter())
    prompt = planner._build_plan_prompt(
        "Fix queue cancellation",
        {
            "project_root": ".",
            "planning_context": {
                "memory_model": "repo-aware-v2",
                "project_knowledge": {
                    "facts": {"framework": "FastAPI"},
                    "reusable_notes": [{"note_type": "constraint", "content": "Do not bypass auth"}],
                    "signals": {},
                },
                "related_runs": [{"run_id": "run-1", "task": "Queue cancellation regression", "status": "completed", "similarity": 0.75}],
                "related_failed_runs": [],
                "avoid_rediscovery": True,
            },
        },
    )

    assert "Reusable project knowledge" in prompt
    assert "Related prior runs ranked by relevance" in prompt
    assert "Avoid rediscovery" in prompt
    assert "Do not bypass auth" in prompt
