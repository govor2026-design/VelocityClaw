from fastapi import FastAPI
from fastapi.testclient import TestClient

from velocity_claw.api.failed_run_resume_v2 import install_failed_run_resume_v2
from velocity_claw.core.failed_run_resume import FailedRunResumeError


class MinimalMemory:
    def load_run(self, run_id):
        return None


class MinimalAgent:
    def __init__(self):
        self.memory = MinimalMemory()

    async def resume_after_approval(self, run_id, step_id):
        return {"status": "legacy"}


class PreviewAgent(MinimalAgent):
    def get_failed_run_resume_state(self, run_id):
        return {
            "run_id": run_id,
            "resumable": True,
            "from_step_id": 2,
            "remaining_step_ids": [2, 3],
        }

    async def resume_failed_run(self, run_id, actor="operator", reason=None):
        return {
            "status": "completed",
            "run_id": run_id,
            "actor": actor,
            "reason": reason,
        }


def build_client(agent):
    app = FastAPI()
    app.state.agent = agent
    install_failed_run_resume_v2(app)
    return TestClient(app)


def test_resume_preview_and_execution_endpoints():
    agent = PreviewAgent()
    client = build_client(agent)
    agent.get_failed_run_resume_state = PreviewAgent.get_failed_run_resume_state.__get__(agent)
    agent.resume_failed_run = PreviewAgent.resume_failed_run.__get__(agent)

    preview = client.get("/runs/run-1/resume/v2")
    executed = client.post(
        "/runs/run-1/resume/v2",
        json={"actor": "owner", "reason": "dependency repaired"},
    )

    assert preview.status_code == 200
    assert preview.json()["resume"]["from_step_id"] == 2
    assert executed.status_code == 200
    assert executed.json()["resume"] == {
        "status": "completed",
        "run_id": "run-1",
        "actor": "owner",
        "reason": "dependency repaired",
    }


def test_resume_preview_maps_missing_run_to_404():
    agent = MinimalAgent()
    client = build_client(agent)

    def missing(run_id):
        raise FailedRunResumeError("run_not_found", "Run not found.", status_code=404)

    agent.get_failed_run_resume_state = missing
    response = client.get("/runs/missing/resume/v2")

    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "run_not_found"


def test_resume_execution_maps_conflict_to_409():
    agent = MinimalAgent()
    client = build_client(agent)

    async def conflict(run_id, actor="operator", reason=None):
        raise FailedRunResumeError(
            "resume_in_progress",
            "A resume is already in progress.",
        )

    agent.resume_failed_run = conflict
    response = client.post("/runs/run-1/resume/v2", json={})

    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "resume_in_progress"
