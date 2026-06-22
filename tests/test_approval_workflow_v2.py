import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from velocity_claw.api.app import install_approval_v2
from velocity_claw.api.approval_v2 import build_approval_detail, build_approval_index, evaluate_approval_decision


RUN_ID = "run-approval"


def make_step(step_id, tool, *, status="pending_approval", risk_level="medium", started_at="2026-05-11T00:00:00Z"):
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
        "id": step_id,
        "title": f"Run {tool}",
        "tool": tool,
        "args": {"path": "demo.py"},
        "status": status,
        "result": approval_record if status == "pending_approval" else None,
        "error": None,
        "started_at": started_at,
        "completed_at": started_at,
    }


def plan_step(step):
    return {
        "id": step["id"],
        "title": step["title"],
        "tool": step["tool"],
        "args": step["args"],
    }


def make_run(
    step_status="pending_approval",
    *,
    run_id=RUN_ID,
    step_id=7,
    tool="patch.apply",
    risk_level="medium",
    started_at="2026-05-11T00:00:00Z",
    continuation_steps=None,
    include_plan=True,
):
    source = make_step(step_id, tool, status=step_status, risk_level=risk_level, started_at=started_at)
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
    source["result"] = approval_record if step_status == "pending_approval" else None
    planned_steps = continuation_steps or [plan_step(source)]
    artifacts = [
        {
            "step_id": step_id,
            "name": f"approval_step_{step_id}",
            "artifact_type": "approval",
            "content": json.dumps(approval_record),
            "created_at": started_at,
        }
    ]
    if include_plan:
        artifacts.append(
            {
                "step_id": None,
                "name": "run_plan",
                "artifact_type": "plan",
                "content": json.dumps({"steps": planned_steps}),
                "created_at": started_at,
            }
        )
    return {
        "run_id": run_id,
        "task": f"Guarded operation with {tool}",
        "status": "awaiting_approval",
        "steps": [source],
        "artifacts": artifacts,
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
        self.saved_steps = []
        self.notes = []

    def load_run(self, run_id):
        if run_id != self.run["run_id"]:
            return None
        return self.run

    def update_step_status(self, run_id, step_id, status, result=None, error=None):
        for step in self.run["steps"]:
            if step["id"] == step_id:
                step["status"] = status
                step["result"] = result
                step["error"] = error

    def save_step(self, run_id, step):
        saved = dict(step)
        self.saved_steps.append(saved)
        self.run["steps"].append(saved)

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
                "created_at": "now",
            }
        )

    def save_project_note(self, note_type, content):
        self.notes.append({"note_type": note_type, "content": content})

    def update_run_status(self, run_id, status):
        self.run["status"] = status


class FakeSettings:
    execution_profile = "safe"


class FakeApprovals:
    def __init__(self, risky_step_ids=None):
        self.risky_step_ids = set(risky_step_ids or [])

    def requires_approval(self, step, profile_name):
        return step.get("id") in self.risky_step_ids

    def build_record(self, step, profile_name):
        return {
            "reason": f"{step.get('tool')} requires review",
            "profile": profile_name,
            "risk_level": "high",
            "approval_label": f"high:{step.get('tool')}",
            "triggers": ["continuation_sensitive_step"],
            "operator_hint": "Review continuation step.",
            "next_step_hint": "Approve or reject the continuation boundary.",
            "recommended_action": "review_then_approve_or_reject",
            "summary": {"tool": step.get("tool")},
        }


class FakeExecutor:
    def __init__(self, results=None):
        self.results = results or {}
        self.calls = []

    async def execute_step(self, step, context):
        self.calls.append(step["id"])
        override = self.results.get(step["id"], {})
        return {
            "id": step["id"],
            "title": step["title"],
            "tool": step.get("tool"),
            "args": step.get("args", {}),
            "status": override.get("status", "success"),
            "result": override.get("result", {"ok": True}),
            "error": override.get("error"),
        }


class FakeAgent:
    def __init__(self, run, *, risky_step_ids=None, executor_results=None):
        self.memory = FakeMemory(run)
        self.settings = FakeSettings()
        self.approvals = FakeApprovals(risky_step_ids)
        self.executor = FakeExecutor(executor_results)

    def list_pending_approvals(self):
        pending = []
        for step in self.memory.run["steps"]:
            if step["status"] != "pending_approval":
                continue
            pending.append(
                {
                    "run_id": self.memory.run["run_id"],
                    "step_id": step["id"],
                    "title": step["title"],
                    "tool": step["tool"],
                    "args": step["args"],
                    "result": step["result"],
                    "started_at": step.get("started_at"),
                    "completed_at": step.get("completed_at"),
                }
            )
        return pending

    def _persist_artifacts(self, run_id, result):
        payload = result.get("result") or {}
        if isinstance(payload, dict) and payload.get("stdout"):
            self.memory.save_artifact(
                run_id,
                f"step_{result['id']}_stdout",
                payload["stdout"],
                step_id=result["id"],
                artifact_type="log",
            )


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


def make_client(run, *, risky_step_ids=None, executor_results=None):
    app = FastAPI()
    app.state.agent = FakeAgent(run, risky_step_ids=risky_step_ids, executor_results=executor_results)
    install_approval_v2(app)
    return TestClient(app), app.state.agent


def test_build_approval_detail_exposes_step_history_artifacts_and_links():
    detail = build_approval_detail(make_run(), 7)

    assert detail["status"] == "ok"
    assert detail["can_decide"] is True
    assert detail["step"]["title"] == "Run patch.apply"
    assert len(detail["history"]) == 1
    assert len(detail["artifacts"]) == 1
    assert detail["continuation"] == []
    assert detail["links"]["approve"].endswith("/approvals/v2/run-approval/7/approve")
    assert detail["links"]["run_detail_v2"] == "/runs/run-approval/detail/v2"
    assert detail["links"]["run_artifacts_v2"] == "/runs/run-approval/artifacts/v2"


def test_evaluate_approval_decision_blocks_non_pending_steps():
    guard = evaluate_approval_decision(make_run(step_status="approved"), 7)

    assert guard.allowed is False
    assert guard.reason == "already_approved"
    assert guard.current_status == "approved"


def test_evaluate_approval_decision_uses_history_after_successful_continuation():
    run = make_run(step_status="success")
    run["approval_history"].append({"step_id": 7, "decision": "approved"})

    guard = evaluate_approval_decision(run, 7)

    assert guard.allowed is False
    assert guard.reason == "already_approved"
    assert guard.current_status == "success"


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
    client, _ = make_client(make_run(risk_level="medium", tool="patch.apply"))

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
    client, _ = make_client(make_run())

    response = client.get(f"/approvals/v2/{RUN_ID}/7")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["approval"]["can_decide"] is True
    assert payload["approval"]["history"][0]["decision"] == "requested"


def test_approval_v2_reject_records_terminal_boundary_and_blocks_second_decision():
    run = make_run()
    client, _ = make_client(run)

    first = client.post(f"/approvals/v2/{RUN_ID}/7/reject", json={"actor": "owner", "reason": "not safe"})
    assert first.status_code == 200
    payload = first.json()
    assert payload["status"] == "ok"
    assert payload["decision"]["boundary"]["continuation_allowed"] is False
    assert run["steps"][0]["status"] == "rejected"
    assert run["status"] == "rejected"
    assert any(item["artifact_type"] == "approval_rejection" for item in run["artifacts"])
    assert payload["approval"]["latest_continuation"]["artifact_type"] == "approval_rejection"

    second = client.post(f"/approvals/v2/{RUN_ID}/7/approve", json={"actor": "owner", "reason": "changed mind"})
    assert second.status_code == 409
    assert second.json()["detail"]["error"] == "already_rejected"


def test_approval_v2_approve_completes_without_duplicate_source_step():
    run = make_run()
    client, agent = make_client(run)

    response = client.post(f"/approvals/v2/{RUN_ID}/7/approve", json={"actor": "owner", "reason": "approved"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["decision"]["decision"] == "approved"
    assert payload["decision"]["resume"]["status"] == "completed"
    assert payload["decision"]["resume"]["executed_step_ids"] == [7]
    assert run["status"] == "completed"
    assert run["steps"][0]["status"] == "success"
    assert len(run["steps"]) == 1
    assert agent.memory.saved_steps == []
    assert payload["approval"]["reason"] == "already_approved"
    assert payload["approval"]["latest_continuation"]["payload"]["status"] == "completed"

    second = client.post(f"/approvals/v2/{RUN_ID}/7/approve", json={"actor": "owner", "reason": "duplicate"})
    assert second.status_code == 409
    assert second.json()["detail"]["error"] == "already_approved"


def test_approval_v2_approve_requires_manual_resume_when_plan_missing():
    run = make_run(include_plan=False)
    client, _ = make_client(run)

    response = client.post(f"/approvals/v2/{RUN_ID}/7/approve", json={"actor": "owner", "reason": "approved"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["decision"]["resume"]["status"] == "manual_resume_required"
    assert payload["decision"]["resume"]["reason"] == "run_plan_missing"
    assert run["status"] == "approved_waiting_manual_resume"
    assert payload["approval"]["latest_continuation"]["payload"]["reason"] == "run_plan_missing"


def test_approval_v2_continuation_pauses_at_next_sensitive_step():
    source = make_step(7, "patch.apply")
    next_step = make_step(8, "shell.run", status="planned", risk_level="high")
    run = make_run(continuation_steps=[plan_step(source), plan_step(next_step)])
    client, agent = make_client(run, risky_step_ids={8})

    response = client.post(f"/approvals/v2/{RUN_ID}/7/approve", json={"actor": "owner", "reason": "approved"})

    assert response.status_code == 200
    payload = response.json()
    resume = payload["decision"]["resume"]
    assert resume["status"] == "awaiting_approval"
    assert resume["boundary_step_id"] == 8
    assert resume["executed_step_ids"] == [7]
    assert run["status"] == "awaiting_approval"
    assert [step["id"] for step in run["steps"]] == [7, 8]
    assert run["steps"][0]["status"] == "success"
    assert run["steps"][1]["status"] == "pending_approval"
    assert [step["id"] for step in agent.memory.saved_steps] == [8]
    assert any(item["artifact_type"] == "approval_boundary" and item["step_id"] == 8 for item in run["artifacts"])


def test_approval_v2_continuation_records_failed_boundary():
    run = make_run()
    client, _ = make_client(
        run,
        executor_results={7: {"status": "failed", "result": None, "error": "execution failed"}},
    )

    response = client.post(f"/approvals/v2/{RUN_ID}/7/approve", json={"actor": "owner", "reason": "approved"})

    assert response.status_code == 200
    payload = response.json()
    resume = payload["decision"]["resume"]
    assert resume["status"] == "failed"
    assert resume["reason"] == "step_execution_failed"
    assert resume["failed_step_id"] == 7
    assert run["status"] == "failed"
    assert run["steps"][0]["status"] == "failed"
    assert payload["approval"]["latest_continuation"]["payload"]["status"] == "failed"
