import asyncio
import json
from pathlib import Path

import pytest

from velocity_claw.config.settings import Settings
from velocity_claw.core.failed_run_resume import (
    FailedRunResumeError,
    install_failed_run_resume_instance,
)
from velocity_claw.memory import MemoryStore


class FakeGuard:
    def __init__(self, *, approval_step=None, fail_step=None, wait_event=None, release_event=None):
        self.approval_step = approval_step
        self.fail_step = fail_step
        self.wait_event = wait_event
        self.release_event = release_event
        self.calls = []

    async def execute(self, step, context, profile_name, *, approved=False, started_at=None):
        self.calls.append(
            {
                "id": step.get("id"),
                "context": context,
                "profile": profile_name,
                "approved": approved,
            }
        )
        if self.wait_event is not None:
            self.wait_event.set()
            await self.release_event.wait()
        if step.get("id") == self.approval_step and not approved:
            return {
                "state": "approval_required",
                "policy": {"profile": profile_name, "mode": "approval"},
                "step_result": None,
            }
        status = "failed" if step.get("id") == self.fail_step else "success"
        result = {
            "id": step.get("id"),
            "title": step.get("title"),
            "tool": step.get("tool"),
            "args": step.get("args", {}),
            "status": status,
            "result": {"ok": status == "success"},
            "error": "resume failed" if status == "failed" else None,
            "started_at": started_at,
            "completed_at": started_at,
            "policy": {
                "profile": profile_name,
                "mode": "allow",
                "approved": approved,
            },
        }
        return {"state": "executed", "policy": result["policy"], "step_result": result}


class FakeApprovals:
    def build_record(self, step, profile_name=None):
        return {
            "required": True,
            "profile": profile_name,
            "tool": step.get("tool"),
            "policy_mode": "approval",
            "reason": "resume approval required",
        }


class FakeAgent:
    def __init__(self, memory, guard):
        self.memory = memory
        self.step_guard = guard
        self.approvals = FakeApprovals()
        self.persisted = []

    def _profile_for_run(self, run):
        return run.get("execution_profile") or "safe"

    def _persist_artifacts(self, run_id, step_result):
        self.persisted.append((run_id, step_result.get("id")))

    async def resume_after_approval(self, run_id, step_id):
        return {"status": "legacy_resume", "run_id": run_id, "step_id": step_id}


def make_memory(tmp_path: Path, monkeypatch, profile="owner"):
    monkeypatch.setenv("VELOCITY_CLAW_ENV", "test")
    monkeypatch.setenv("VELOCITY_CLAW_MEMORY_DB_PATH", str(tmp_path / "memory.db"))
    monkeypatch.setenv("VELOCITY_CLAW_EXECUTION_PROFILE", profile)
    monkeypatch.setenv("VELOCITY_CLAW_SHELL_ENABLED", "true")
    monkeypatch.setenv("VELOCITY_CLAW_GIT_ENABLED", "true")
    return MemoryStore(Settings())


def plan_steps():
    return [
        {"id": 1, "title": "Inspect", "tool": "analysis", "args": {"prompt": "inspect"}},
        {"id": 2, "title": "Repair", "tool": "analysis", "args": {"prompt": "repair"}},
        {"id": 3, "title": "Verify", "tool": "analysis", "args": {"prompt": "verify"}},
    ]


def seed_failed_run(memory):
    run_id = memory.create_run("Resume original trace")
    memory.save_artifact(
        run_id,
        "run_plan",
        json.dumps({"task": "Resume original trace", "steps": plan_steps()}),
        artifact_type="plan",
    )
    memory.save_artifact(
        run_id,
        "planning_context",
        json.dumps({"project_root": ".", "original": True}),
        artifact_type="planning_context",
    )
    memory.save_step(
        run_id,
        {
            **plan_steps()[0],
            "status": "success",
            "result": {"inspected": True},
            "error": None,
        },
    )
    memory.save_step(
        run_id,
        {
            **plan_steps()[1],
            "status": "failed",
            "result": None,
            "error": "initial failure",
        },
    )
    memory.update_run_status(run_id, "failed")
    return run_id


def test_preview_identifies_failed_boundary_and_skipped_steps(tmp_path: Path, monkeypatch):
    memory = make_memory(tmp_path, monkeypatch)
    run_id = seed_failed_run(memory)
    agent = FakeAgent(memory, FakeGuard())
    install_failed_run_resume_instance(agent)

    preview = agent.get_failed_run_resume_state(run_id)

    assert preview["resumable"] is True
    assert preview["from_step_id"] == 2
    assert preview["remaining_step_ids"] == [2, 3]
    assert preview["skipped_completed_step_ids"] == [1]
    assert preview["next_attempt_no"] == 2
    assert preview["execution_profile"] == "owner"


def test_resume_retries_failed_step_and_continues_same_run(tmp_path: Path, monkeypatch):
    async def scenario():
        memory = make_memory(tmp_path, monkeypatch)
        run_id = seed_failed_run(memory)
        guard = FakeGuard()
        agent = FakeAgent(memory, guard)
        install_failed_run_resume_instance(agent)

        result = await agent.resume_failed_run(run_id, actor="owner", reason="fixed dependency")
        run = memory.load_run(run_id)

        assert result["status"] == "completed"
        assert result["run_id"] == run_id
        assert [item["id"] for item in result["executed"]] == [2, 3]
        assert [item["id"] for item in guard.calls] == [2, 3]
        assert all(item["context"]["original"] is True for item in guard.calls)
        assert run["status"] == "completed"
        assert len(run["steps"]) == 4
        assert run["forensics"]["failed_step"] is None
        assert run["forensics"]["step_attempts"]["retried_steps"] == ["2"]
        assert any(item["artifact_type"] == "resume_boundary" for item in run["artifacts"])
        assert any(item["artifact_type"] == "resume_summary" for item in run["artifacts"])
        retried = [item for item in run["steps"] if item["id"] == 2]
        assert [item["status"] for item in retried] == ["failed", "success"]
        assert [item["attempt_no"] for item in retried] == [1, 2]
        assert retried[-1]["phase"] == "failed_resume"

    asyncio.run(scenario())


def test_resume_failure_stays_failed_and_preserves_attempt_history(tmp_path: Path, monkeypatch):
    async def scenario():
        memory = make_memory(tmp_path, monkeypatch)
        run_id = seed_failed_run(memory)
        agent = FakeAgent(memory, FakeGuard(fail_step=2))
        install_failed_run_resume_instance(agent)

        result = await agent.resume_failed_run(run_id)
        run = memory.load_run(run_id)

        assert result["status"] == "failed"
        assert run["status"] == "failed"
        attempts = [item for item in run["steps"] if item["id"] == 2]
        assert len(attempts) == 2
        assert attempts[-1]["attempt_no"] == 2
        assert attempts[-1]["error"] == "resume failed"
        assert run["forensics"]["failed_step"]["id"] == 2

    asyncio.run(scenario())


def test_second_resume_is_rejected_while_first_is_running(tmp_path: Path, monkeypatch):
    async def scenario():
        memory = make_memory(tmp_path, monkeypatch)
        run_id = seed_failed_run(memory)
        started = asyncio.Event()
        release = asyncio.Event()
        agent = FakeAgent(memory, FakeGuard(wait_event=started, release_event=release))
        install_failed_run_resume_instance(agent)

        first = asyncio.create_task(agent.resume_failed_run(run_id))
        await started.wait()
        with pytest.raises(FailedRunResumeError) as exc:
            await agent.resume_failed_run(run_id)
        assert exc.value.code == "resume_in_progress"
        release.set()
        assert (await first)["status"] == "completed"

    asyncio.run(scenario())


def test_resume_approval_continues_through_wrapped_approval_path(tmp_path: Path, monkeypatch):
    async def scenario():
        memory = make_memory(tmp_path, monkeypatch, profile="dev")
        run_id = seed_failed_run(memory)
        guard = FakeGuard(approval_step=2)
        agent = FakeAgent(memory, guard)
        install_failed_run_resume_instance(agent)

        paused = await agent.resume_failed_run(run_id)
        assert paused["status"] == "awaiting_approval"
        assert paused["boundary_step_id"] == 2

        memory.update_step_status(run_id, 2, "approved", result={"decision": "approved"})
        continued = await agent.resume_after_approval(run_id, 2)
        run = memory.load_run(run_id)

        assert continued["status"] == "completed"
        assert [item["id"] for item in continued["executed"]] == [2, 3]
        assert guard.calls[-2]["approved"] is True
        assert run["status"] == "completed"
        attempts = [item for item in run["steps"] if item["id"] == 2]
        assert attempts[0]["status"] == "failed"
        assert attempts[1]["status"] == "approved"
        assert attempts[-1]["status"] == "success"
        assert all(item["phase"] == "failed_resume" for item in attempts[1:])

    asyncio.run(scenario())
