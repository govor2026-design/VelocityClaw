from velocity_claw.api import approval_v2
from velocity_claw.api.approval_attempts_v2 import install_latest_step_lookup


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
                "attempt_no": 2,
                "phase": "failed_resume",
            },
        ],
        "artifacts": [],
        "approval_history": [
            {"step_id": 2, "decision": "requested"},
        ],
    }


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
