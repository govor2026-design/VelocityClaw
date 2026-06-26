import json

from velocity_claw.api.run_detail_v2 import build_run_detail_v2, build_step_index


def resumed_run():
    return {
        "run_id": "resumed-run",
        "task": "Resume failed workflow",
        "status": "completed",
        "execution_profile": "dev",
        "created_at": "start",
        "completed_at": "end",
        "steps": [
            {
                "record_id": 1,
                "id": 1,
                "title": "Inspect",
                "tool": "analysis",
                "status": "success",
                "attempt_no": 1,
                "phase": "initial",
            },
            {
                "record_id": 2,
                "id": 2,
                "title": "Repair",
                "tool": "analysis",
                "status": "failed",
                "error": "first failure",
                "attempt_no": 1,
                "phase": "initial",
            },
            {
                "record_id": 3,
                "id": 2,
                "title": "Repair",
                "tool": "analysis",
                "status": "success",
                "attempt_no": 2,
                "phase": "failed_resume",
            },
        ],
        "artifacts": [
            {
                "name": "run_plan",
                "artifact_type": "plan",
                "step_id": None,
                "content": json.dumps({"steps": [{"id": 1}, {"id": 2}]}),
            },
            {
                "name": "failed_resume_boundary_1",
                "artifact_type": "resume_boundary",
                "step_id": 2,
                "content": json.dumps({"resume_number": 1, "from_step_id": 2}),
            },
            {
                "name": "failed_resume_summary_1",
                "artifact_type": "resume_summary",
                "step_id": 2,
                "content": json.dumps({"resume_number": 1, "status": "completed"}),
            },
        ],
        "approval_history": [],
        "report": {"executive_summary": "Run completed after resume."},
        "forensics": {
            "failed_step": None,
            "pending_approval_step": None,
            "last_step": {"id": 2, "status": "success"},
            "artifact_counts_by_type": {"plan": 1, "resume_boundary": 1, "resume_summary": 1},
            "step_attempts": {"retried_steps": ["2"]},
        },
    }


def test_step_index_separates_effective_steps_from_attempt_records():
    index = build_step_index(resumed_run())

    assert index["total"] == 2
    assert index["total_attempt_records"] == 3
    assert index["status_counts"] == {"success": 2}
    assert index["failed_steps"] == []
    assert index["attempt_summary"]["retried_steps"] == ["2"]
    assert len(index["history_by_step"]["2"]) == 2
    assert index["items"][1]["attempt_no"] == 2
    assert index["items"][1]["phase"] == "failed_resume"


def test_run_detail_exposes_resume_history_and_links():
    detail = build_run_detail_v2(resumed_run())

    assert detail["execution_profile"] == "dev"
    assert detail["resume"]["resumable"] is False
    assert detail["resume"]["resume_count"] == 1
    assert detail["resume"]["latest_boundary"]["from_step_id"] == 2
    assert detail["resume"]["latest_summary"]["status"] == "completed"
    assert detail["links"]["resume_v2"] == "/runs/resumed-run/resume/v2"
    assert detail["forensic_highlights"]["step_attempts"]["retried_steps"] == ["2"]
