from velocity_claw.core.failed_run_resume import FailedRunResumer


def test_approved_resume_reuses_pending_attempt_number():
    records = [
        {"id": 2, "status": "failed", "attempt_no": 1, "phase": "initial"},
        {"id": 2, "status": "approved", "attempt_no": 2, "phase": "failed_resume"},
    ]

    attempt = FailedRunResumer._attempt_for_step(
        records,
        2,
        reuse_approval_attempt=True,
    )

    assert attempt == 2


def test_non_approval_retry_increments_latest_attempt_number():
    records = [
        {"id": 2, "status": "failed", "attempt_no": 1, "phase": "initial"},
        {"id": 2, "status": "failed", "attempt_no": 2, "phase": "failed_resume"},
    ]

    attempt = FailedRunResumer._attempt_for_step(records, 2)

    assert attempt == 3
