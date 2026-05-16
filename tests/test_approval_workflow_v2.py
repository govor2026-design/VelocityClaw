import asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient

from velocity_claw.api.app import install_approval_v2
from velocity_claw.api.approval_v2 import build_approval_detail, evaluate_approval_decision


RUN_ID = "run-approval"


def make_run(step_status="pending_approval"):
    return {
        "run_id": RUN_ID,
        "task": "Apply guarded patch",
        "status": "awaiting_approval",
        "steps": [
            {
                "id": 7,
                "title": "Apply patch",
                "tool": "patch.apply",
                "args": {"path": "demo.py"},
                "status": step_status,
                "result": {"reason": "patch requires review"},
                "error": None,
            }
        ],
        "artifacts": [
            {
                "step_id": 7,
                "name": "approval_step_7",
                "artifact_type": "approval",
                "content": "{}",
            }
        ],
        "approval_history": [
            {
                "step_id": 7,
                "decision": "requested",
                "actor": None,
                "reason": "patch requires review",
                "payload": {"reason": "patch requires review"},
                "created_at": "2026-05-11T00:00:00Z",
            }
        ],
    }


class FakeMemory:
    def __init__(self, run):
        self.run = run

    def load_run(self, run_id):
        if run_id != RUN_ID:
            return None
        return self.run

    def update_step_status(self, run_id, step_id, status, result=None, error=None):
        self.run["steps"][0]["status"] = status
        self.run["steps"][0]["result"] = result
        self.run["steps"][0]["error"] = error

    def save_approval_decision(self, run_id, step_id, decision, actor=None, reason=None, payload=None):
        self.run["approval_history"].append(
            {
                "step_id": step_id,
                "decision": decision,
                "actor": actor,
                "reason": reason,
                "payload": payload,
                "created_at": "now",
            }
        )

    def save_artifact(self, run_id, name, content, step_id=None, artifact_type="text"):
        self.run["artifacts"].append(
            {
                "step_id": step_id,
                "name": name,
                "artifact_type": artifact_type,
                "content": content,
            }
        )

    def save_project_note(self, note_type, content):
        pass

    def update_run_status(self, run_id, status):
        self.run["status"] = status


class FakeAgent:
    def __init__(self, run):
        self.memory = FakeMemory(run)

    async def approve_step(self, run_id, step_id, actor="owner", reason=None):
        self.memory.update_step_status(run_id, step_id, "approved", result={"decision": "approved", "actor": actor, "reason": reason})
        self.memory.save_approval_decision(run_id, step_id, "approved", actor=actor, reason=reason, payload={"decision": "approved"})
        return {"decision": "approved", "actor": actor, "reason": reason, "resume": {"status": "completed"}}

    def reject_step(self, run_id, step_id, actor="owner", reason=None):
        self.memory.update_step_status(run_id, step_id, "rejected", result={"decision": "rejected", "actor": actor, "reason": reason}, error="Rejected by reviewer")
        self.memory.save_approval_decision(run_id, step_id, "rejected", actor=actor, reason=reason, payload={"decision": "rejected"})
        self.memory.update_run_status(run_id, "rejected")
        return {"decision": "rejected", "actor": actor, "reason": reason}


def make_client(run):
    app = FastAPI()
    app.state.agent = FakeAgent(run)
    install_approval_v2(app)
    return TestClient(app)


def test_build_approval_detail_exposes_step_history_artifacts_and_links():
    detail = build_approval_detail(make_run(), 7)

    assert detail["status"] == "ok"
    assert detail["can_decide"] is True
    assert detail["step"]["title"] == "Apply patch"
    assert len(detail["history"]) == 1
    assert len(detail["artifacts"]) == 1
    assert detail["links"]["approve"].endswith("/approvals/v2/run-approval/7/approve")


def test_evaluate_approval_decision_blocks_non_pending_steps():
    guard = evaluate_approval_decision(make_run(step_status="approved"), 7)

    assert guard.allowed is False
    assert guard.reason == "already_approved"
    assert guard.current_status == "approved"


def test_approval_detail_v2_endpoint_returns_context():
    client = make_client(make_run())

    response = client.get(f"/approvals/v2/{RUN_ID}/7")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["approval"]["can_decide"] is True
    assert payload["approval"]["history"][0]["decision"] == "requested"


def test_approval_v2_reject_changes_status_and_blocks_second_decision():
    run = make_run()
    client = make_client(run)

    first = client.post(f"/approvals/v2/{RUN_ID}/7/reject", json={"actor": "owner", "reason": "not safe"})
    assert first.status_code == 200
    assert first.json()["status"] == "ok"
    assert run["steps"][0]["status"] == "rejected"
    assert run["status"] == "rejected"

    second = client.post(f"/approvals/v2/{RUN_ID}/7/approve", json={"actor": "owner", "reason": "changed mind"})
    assert second.status_code == 409
    assert second.json()["detail"]["error"] == "already_rejected"


def test_approval_v2_approve_returns_resume_payload():
    run = make_run()
    client = make_client(run)

    response = client.post(f"/approvals/v2/{RUN_ID}/7/approve", json={"actor": "owner", "reason": "approved"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["decision"]["decision"] == "approved"
    assert payload["decision"]["resume"]["status"] == "completed"
    assert run["steps"][0]["status"] == "approved"
