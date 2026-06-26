from velocity_claw.api.approval_v2 import build_approval_detail, evaluate_approval_decision


def retried_run() -> dict:
    return {
        "run_id": "run-1",
        "status": "awaiting_approval",
        "task": "Resume repair",
        "steps": [
            {
                "id": 2,
                "status": "failed",
                "attempt_no": 1,
                "phase": "initial",
                "error": "old failure",
            },
            {
                "id": 2,
                "status": "pending_approval",
                "attempt_no": 2,
                "phase": "failed_resume",
                "error": None,
            },
        ],
        "artifacts": [],
        "approval_history": [{"step_id": 2, "decision": "requested"}],
    }


def test_directly_imported_detail_uses_latest_attempt() -> None:
    run = retried_run()

    detail = build_approval_detail(run, 2)

    assert detail["can_decide"] is True
    assert detail["current_status"] == "pending_approval"
    assert detail["step"]["attempt_no"] == 2
    assert detail["step"]["phase"] == "failed_resume"


def test_native_guard_uses_latest_attempt_without_installation() -> None:
    guard = evaluate_approval_decision(retried_run(), 2)

    assert guard.allowed is True
    assert guard.reason == "pending_approval"
    assert guard.current_status == "pending_approval"
