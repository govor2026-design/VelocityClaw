from fastapi import FastAPI
from fastapi.testclient import TestClient

from velocity_claw.api.app import install_run_detail_v2
from velocity_claw.api.run_detail_v2 import build_artifact_index, build_run_detail_v2, build_step_index


RUN_ID = "run-detail-1"


def make_run():
    return {
        "run_id": RUN_ID,
        "task": "Fix failing tests",
        "status": "failed",
        "created_at": "2026-05-16T00:00:00Z",
        "completed_at": "2026-05-16T00:05:00Z",
        "steps": [
            {"id": 1, "title": "Inspect", "tool": "fs.read", "status": "success", "error": None, "started_at": "a", "completed_at": "b"},
            {"id": 2, "title": "Apply patch", "tool": "patch.apply", "status": "pending_approval", "error": None, "started_at": "b", "completed_at": "c"},
            {"id": 3, "title": "Run tests", "tool": "test.run", "status": "failed", "error": "pytest failed", "started_at": "c", "completed_at": "d"},
        ],
        "artifacts": [
            {"step_id": None, "name": "run_plan", "artifact_type": "plan", "content": "{}", "created_at": "now"},
            {"step_id": 2, "name": "approval_step_2", "artifact_type": "approval", "content": "approval payload", "created_at": "now"},
            {"step_id": 3, "name": "step_3_stdout", "artifact_type": "log", "content": "x" * 500, "created_at": "now"},
        ],
        "approval_history": [
            {"step_id": 2, "decision": "requested", "actor": None, "reason": "patch requires review", "created_at": "now"}
        ],
        "report": {"executive_summary": "Run failed after test execution."},
        "forensics": {
            "failed_step": {"id": 3, "title": "Run tests", "tool": "test.run", "error": "pytest failed"},
            "pending_approval_step": {"id": 2, "title": "Apply patch", "tool": "patch.apply"},
            "last_step": {"id": 3, "title": "Run tests", "tool": "test.run", "status": "failed"},
            "artifact_counts_by_type": {"plan": 1, "approval": 1, "log": 1},
        },
    }


class FakeMemory:
    def __init__(self, run):
        self.run = run

    def load_run(self, run_id):
        if run_id == RUN_ID:
            return self.run
        return None


class FakeAgent:
    def __init__(self, run):
        self.memory = FakeMemory(run)


def make_client(run):
    app = FastAPI()
    app.state.agent = FakeAgent(run)
    install_run_detail_v2(app)
    return TestClient(app)


def test_build_artifact_index_groups_by_type_and_step_with_previews():
    index = build_artifact_index(make_run())

    assert index["total"] == 3
    assert index["counts_by_type"] == {"plan": 1, "approval": 1, "log": 1}
    assert index["by_step"]["run_level"][0]["name"] == "run_plan"
    assert index["by_step"]["step_3"][0]["content_size"] == 500
    assert len(index["by_step"]["step_3"][0]["content_preview"]) == 240


def test_build_step_index_exposes_failed_and_pending_steps():
    index = build_step_index(make_run())

    assert index["total"] == 3
    assert index["status_counts"]["success"] == 1
    assert index["status_counts"]["pending_approval"] == 1
    assert index["status_counts"]["failed"] == 1
    assert index["failed_steps"][0]["id"] == 3
    assert index["pending_approval_steps"][0]["approval_detail_url"] == f"/approvals/v2/{RUN_ID}/2"


def test_build_run_detail_v2_returns_compact_operational_summary():
    detail = build_run_detail_v2(make_run())

    assert detail["run_id"] == RUN_ID
    assert detail["task"] == "Fix failing tests"
    assert detail["summary"] == "Run failed after test execution."
    assert detail["approval_events"] == 1
    assert detail["artifact_index"]["total"] == 3
    assert detail["forensic_highlights"]["failed_step"]["id"] == 3
    assert detail["links"]["detail_v2"] == f"/runs/{RUN_ID}/detail/v2"


def test_run_detail_v2_endpoint_returns_summary():
    client = make_client(make_run())

    response = client.get(f"/runs/{RUN_ID}/detail/v2")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["run"]["run_id"] == RUN_ID
    assert payload["run"]["step_index"]["failed_steps"][0]["error"] == "pytest failed"


def test_run_artifacts_v2_endpoint_returns_index():
    client = make_client(make_run())

    response = client.get(f"/runs/{RUN_ID}/artifacts/v2")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["run_id"] == RUN_ID
    assert payload["artifacts"]["counts_by_type"]["approval"] == 1


def test_run_detail_v2_endpoint_returns_404_for_missing_run():
    client = make_client(make_run())

    response = client.get("/runs/missing/detail/v2")

    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "not_found"
