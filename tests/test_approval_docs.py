from pathlib import Path


APPROVAL_DOC = Path("docs/APPROVALS.md")


def test_approval_docs_cover_v3_outcomes_and_artifacts():
    content = APPROVAL_DOC.read_text(encoding="utf-8")

    required = [
        "Approval continuation v3",
        "completed",
        "failed",
        "awaiting_approval",
        "manual_resume_required",
        "policy_validation_failed",
        "step_execution_failed",
        "approval_continuation",
        "approval_rejection",
        "continuation_allowed",
        "/approvals/v2/{run_id}/{step_id}/approve",
        "/approvals/v2/{run_id}/{step_id}/reject",
    ]
    for value in required:
        assert value in content
