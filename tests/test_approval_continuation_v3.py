import asyncio
import json

from velocity_claw.core.approval_continuation import continue_after_approval


class Memory:
    def __init__(self):
        self.run = {
            "run_id": "run-policy",
            "task": "Run blocked shell step",
            "status": "resuming_after_approval",
            "steps": [
                {
                    "id": 1,
                    "title": "Run shell",
                    "tool": "shell.run",
                    "args": {"command": "echo blocked"},
                    "status": "approved",
                    "result": {"decision": "approved"},
                    "error": None,
                }
            ],
            "artifacts": [
                {
                    "step_id": None,
                    "name": "run_plan",
                    "artifact_type": "plan",
                    "content": json.dumps(
                        {
                            "steps": [
                                {
                                    "id": 1,
                                    "title": "Run shell",
                                    "tool": "shell.run",
                                    "args": {"command": "echo blocked"},
                                }
                            ]
                        }
                    ),
                }
            ],
            "approval_history": [{"step_id": 1, "decision": "approved"}],
        }
        self.notes = []

    def load_run(self, run_id):
        return self.run if run_id == self.run["run_id"] else None

    def update_step_status(self, run_id, step_id, status, result=None, error=None):
        step = self.run["steps"][0]
        step["status"] = status
        step["result"] = result
        step["error"] = error

    def save_step(self, run_id, step):
        self.run["steps"].append(step)

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
        self.notes.append((note_type, content))

    def update_run_status(self, run_id, status):
        self.run["status"] = status


class ProfileManager:
    def is_tool_allowed(self, tool, profile_name):
        return False


class Approvals:
    def requires_approval(self, step, profile_name):
        return False


class Executor:
    def __init__(self):
        self.called = False

    async def execute_step(self, step, context):
        self.called = True
        return {"id": step["id"], "status": "success", "result": {"ok": True}, "error": None}


class Settings:
    execution_profile = "safe"


class Agent:
    def __init__(self):
        self.memory = Memory()
        self.profile_manager = ProfileManager()
        self.approvals = Approvals()
        self.executor = Executor()
        self.settings = Settings()

    def _persist_artifacts(self, run_id, result):
        pass


def test_continuation_rechecks_profile_policy_before_executor():
    agent = Agent()

    result = asyncio.run(continue_after_approval(agent, "run-policy", 1))

    assert result["status"] == "failed"
    assert result["reason"] == "policy_validation_failed"
    assert result["failed_step_id"] == 1
    assert agent.executor.called is False
    assert agent.memory.run["status"] == "failed"
    assert agent.memory.run["steps"][0]["status"] == "failed"
    assert "not allowed in profile safe" in agent.memory.run["steps"][0]["error"]
    continuation = [
        artifact
        for artifact in agent.memory.run["artifacts"]
        if artifact["artifact_type"] == "approval_continuation"
    ]
    assert len(continuation) == 1
    assert json.loads(continuation[0]["content"])["reason"] == "policy_validation_failed"
