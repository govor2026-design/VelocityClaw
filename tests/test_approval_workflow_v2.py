from fastapi import FastAPI
from fastapi.testclient import TestClient

from velocity_claw.api.app import install_approval_v2
from velocity_claw.api.approval_v2 import build_approval_detail, build_approval_index, evaluate_approval_decision


RUN_ID = "run-approval"


def make_run(
    step_status="pending_approval",
    *,
    run_id=RUN_ID,
    step_id=7,
    tool="patch.apply",
    risk_level="medium",
    started_at="2026-05-11T00:00:00Z",
):
    approval_record = {
        "reason": f"{tool} requires review",
        "profile": "safe",
        "risk_level": risk_level,
        "approval_label": f"{risk_level}:{tool}",
        "triggers": ["safe_profile_sensitive_write_or_exec"],
        "operator_hint": f"Review {tool} before continuing.",
        "next_step_hint": f"If approved, {tool} will execute.",
        "recommended_action": "review_then_approve_or_reject",
        "summary": {"tool": tool, "path": "demo.py", "command": None},
    }
    return {
        "run_id": run_id,
        "task": f"Guarded operation with {tool}",
        "status": "awaiting_approval",
        "steps": [
            {
                "id": step_id,
                "title": f"Run {tool}",
                "tool": tool,
                "args": {"path": "demo.py"},
                "status": step_status,
                "result": approval_record,
                "error": None,
                "started_at": started_at,
                "completed_at": started_at,
            }
        ],
        "artifacts": [
            {
                "step_id": step_id,
                "name": f"approval_step_{step_id}",
                "artifact_type": "approval",
                "content": "{}",
            }
        ],
        "approval_history": [
            {
                "step_id": step_id,
                "decision": "requested",
                "actor": None,
                "reason": approval_record["reason"],
                "payload": approval_record,
                "created_at": started_at,
            }
        ],
    }


class FakeMemory:
    def __init__(self, run):
        self.run = run

    def load_run(self, run_id):
        if run_id != self.run["run_id"]:
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

    def list_pending_approvals(self):
        step = self.memory.run["steps"][0]
        if step["status"] != "pending_approval":
            return []
        return [
            {
                "run_id": self.memory.run["run_id"],
                "step_id": step["id"],
                "title": step["title"],
                "tool": step["tool"],
                "args": step["args"],
                "result": step["result"],
                "started_at": step["started_at"],
                "completed_at": step["completed_at"],
            }
        ]

    async def approve_step(self, run_id, step_id, actor="owner", reason=None):
        self.memory.update_step_status(run_id, step_id, "approved", result={"decision": "approved", "actor": actor, "reason": reason})
        self.memory.save_approval_decision(run_id, step_id, "approved", actor=actor, reason=reason, payload={"decision": "approved"})
        return {"decision": "approved", "actor": actor, "reason": reason, "resume": {"status": "completed"}}

    def reject_step(self, run_id, step_id, actor="owner", reason=None):
        self.memory.update_step_status(run_id, step_id, "rejected", result={"decision": "rejected", "actor": actor, "reason": reason}, error="Rejected by reviewer")
        self.memory.save_approval_decision(run_id, step_id, "rejected", actor=actor, reason=reason, payload={"decision": "rejected"})
        self.memory.update_run_status(run_id, "rejected")
        return {"decision": "rejected", "actor": actor, "reason": reason}


class MultiMemory:
    def __init__(self, runs):
        self.runs = {run["run_id"]: run for run in runs}

    def load_run(self, run_id):
        return self.runs.get(run_id)


class MultiAgent:
    def __init__(self, runs):
        self.memory = MultiMemory(runs)

    def list_pending_approvals(self):
        pending = []
        for run in self.memory.runs.values():
            for step in run["steps"]:
                if step["status"] != "pending_approval":
                    continue
                pending.append(
                    {
                        "run_id": run["run_id"],
                        "step_id": step["id"],
                        "title": step["title"],
                        "tool": step["tool"],
                        "args": step["args"],
                        "result": step["result"],
                        "started_at": step["started_at"],
                        "completed_at": step["completed_at"],
                    }
                )
        return pending


def make_client(run):
    app = FastAPI()
    app.state.agent = FakeAgent(run)
    install_approval_v2(app)
    return TestClient(app)


def test_build_approval_detail_exposes_step_history_artifacts_and_links():
    detail = build_approval_detail(make_run(), 7)

    assert detail["status"] == "ok"
    assert detail["can_decide"] is True
    assert detail["step"]["title"] == "Run patch.apply"
    assert len(detail["history"]) == 1
    assert len(detail["artifacts"]) == 1
    assert detail["links"]["approve"].endswith("/approvals/v2/run-approval/7/approve")
    assert detail["links"]["run_detail_v2"] == "/runs/run-approval/detail/v2"
    assert detail["links"]["run_artifacts_v2"] == "/runs/run-approval/artifacts/v2"


def test_evaluate_approval_decision_blocks_non_pending_steps():
    guard = evaluate_approval_decision(make_run(step_status="approved"), 7)

    assert guard.allowed is False
    assert guard.reason == "already_approved"
    assert guard.current_status == "approved"


def test_build_approval_index_summarizes_and_sorts_high_risk_first():
    agent = MultiAgent(
        [
            make_run(run_id="run-low", step_id=1, tool="test.run", risk_level="low", started_at="2026-05-11T00:00:00Z"),
            make_run(run_id="run-high", step_id=2, tool="shell.run", risk_level="high", started_at="2026-05-12T00:00:00Z"),
            make_run(run_id="run-medium", step_id=3, tool="patch.apply", risk_level="medium", started_at="2026-05-10T00:00:00Z"),
        ]
    )

    index = build_approval_index(agent)

    assert index["status"] == "ok"
    assert index["summary"]["total_pending"] == 3
    assert index["summary"]["decidable"] == 3
    assert index["summary"]["counts_by_risk"] == {"high": 1, "medium": 1, "low": 1}
    assert index["summary"]["counts_by_tool"]["shell.run"] == 1
    assert [item["risk_level"] for item in index["items"]] == ["high", "medium", "low"]
    assert index["items"][0]["run_id"] == "run-high"
    assert index["items"][0]["history_count"] == 1
    assert index["items"][0]["artifact_count"] == 1
    assert index["items"][0]["links"]["approve"].endswith("/run-high/2/approve")


def test_build_approval_index_filters_by_risk_tool_and_clamps_limit():
    agent = MultiAgent(
        [
            make_run(run_id="run-shell", step_id=1, tool="shell.run", risk_level="high"),
            make_run(run_id="run-git", step_id=2, tool="git.run", risk_level="high"),
            make_run(run_id="run-patch", step_id=3, tool="patch.apply", risk_level="medium"),
        ]
    )

    filtered = build_approval_index(agent, risk="HIGH", tool="shell.run", limit=500)

    assert filtered["summary"]["total_pending"] == 3
    assert filtered["summary"]["matched"] == 1
    assert filtered["summary"]["returned"] == 1
    assert filtered["filters"] == {"risk": "high", "tool": "shell.run", "limit": 100}
    assert filtered["items"][0]["run_id"] == "run-shell"


def test_approval_index_v2_endpoint_returns_filtered_operator_summary():
    client = make_client(make_run(risk_level="medium", tool="patch.apply"))

    response = client.get("/approvals/v2?risk=medium&tool=patch.apply&limit=1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["summary"]["total_pending"] == 1
    assert payload["summary"]["matched"] == 1
    assert payload["items"][0]["risk_level"] == "medium"
    assert payload["items"][0]["tool"] == "patch.apply"
    assert payload["items"][0]["history_count"] == 1
    assert payload["items"][0]["artifact_count"] == 1


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
