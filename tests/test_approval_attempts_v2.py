import asyncio

from velocity_claw.api import approval_v2
from velocity_claw.api.approval_attempts_v2 import (
    INSTALLATION_FLAG,
    LATEST_STEP_LOOKUP,
    find_latest_step,
    install_latest_step_lookup,
)


def run_with_attempts():
    return {
        "run_id": "run-1",
        "status": "awaiting_approval",
        "task": "Resume repair",
        "steps": [
            {
                "record_id": 1,
                "id": 2,
                "title": "Repair",
                "tool": "shell.run",
                "status": "failed",
                "error": "old failure",
                "attempt_no": 1,
                "phase": "initial",
            },
            {
                "record_id": 2,
                "id": 2,
                "title": "Repair",
                "tool": "shell.run",
                "status": "pending_approval",
                "result": {"risk_level": "high", "profile": "dev"},
                "error": None,
                "attempt_no": 2,
                "phase": "failed_resume",
            },
        ],
        "artifacts": [],
        "approval_history": [
            {"step_id": 2, "decision": "requested"},
        ],
    }


def test_find_latest_step_prefers_most_recent_attempt():
    latest = find_latest_step(run_with_attempts(), 2)

    assert latest["attempt_no"] == 2
    assert latest["phase"] == "failed_resume"


def test_installation_exposes_public_extension_state_and_is_idempotent():
    native_lookup = approval_v2._find_step

    install_latest_step_lookup(approval_v2)
    installed_wrapper = approval_v2.approve_and_continue

    install_latest_step_lookup(approval_v2)

    assert getattr(approval_v2, INSTALLATION_FLAG) is True
    assert getattr(approval_v2, LATEST_STEP_LOOKUP) is find_latest_step
    assert approval_v2.approve_and_continue is installed_wrapper
    assert approval_v2._find_step is native_lookup


def test_approval_guard_uses_latest_attempt_for_retried_step():
    install_latest_step_lookup(approval_v2)

    detail = approval_v2.build_approval_detail(run_with_attempts(), 2)

    assert detail["can_decide"] is True
    assert detail["current_status"] == "pending_approval"
    assert detail["step"]["attempt_no"] == 2
    assert detail["step"]["phase"] == "failed_resume"
    assert detail["step"]["error"] is None


def test_latest_non_pending_attempt_blocks_duplicate_decision():
    install_latest_step_lookup(approval_v2)
    run = run_with_attempts()
    run["steps"][-1]["status"] = "approved"
    run["approval_history"].append({"step_id": 2, "decision": "approved"})

    guard = approval_v2.evaluate_approval_decision(run, 2)

    assert guard.allowed is False
    assert guard.reason == "already_approved"
    assert guard.current_status == "approved"


def test_approval_v2_routes_failed_resume_to_agent_approval_wrapper():
    class Memory:
        def __init__(self):
            self.run = run_with_attempts()

        def load_run(self, run_id):
            return self.run

    class Agent:
        def __init__(self):
            self.memory = Memory()
            self.calls = []

        async def approve_step(self, run_id, step_id, actor="owner", reason=None):
            self.calls.append((run_id, step_id, actor, reason))
            return {
                "decision": "approved",
                "resume": {"status": "completed", "run_id": run_id},
            }

    async def scenario():
        install_latest_step_lookup(approval_v2)
        agent = Agent()

        result = await approval_v2.approve_with_guard(
            agent,
            "run-1",
            2,
            actor="operator",
            reason="reviewed",
        )

        assert result["status"] == "ok"
        assert agent.calls == [("run-1", 2, "operator", "reviewed")]
        assert result["decision"]["resume"]["status"] == "completed"

    asyncio.run(scenario())
