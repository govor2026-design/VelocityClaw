import asyncio
import json

from velocity_claw.config.settings import Settings
from velocity_claw.core.agent import VelocityClawAgent
from velocity_claw.core.step_guard import StepExecutionGuard
from velocity_claw.security.access import ApprovalManager, ExecutionProfileManager


class FakeMemory:
    def __init__(self, run):
        self.run = run
        self.saved_steps = []
        self.saved_artifacts = []
        self.statuses = []
        self.notes = []
        self.approval_events = []

    def load_run(self, run_id):
        return self.run if run_id == self.run["run_id"] else None

    def save_step(self, run_id, result):
        self.saved_steps.append((run_id, result))

    def save_artifact(self, run_id, name, content, step_id=None, artifact_type="text"):
        self.saved_artifacts.append((run_id, name, content, step_id, artifact_type))

    def update_run_status(self, run_id, status):
        self.statuses.append((run_id, status))

    def save_project_note(self, note_type, content):
        self.notes.append((note_type, content))

    def save_approval_decision(self, run_id, step_id, decision, actor=None, reason=None, payload=None):
        self.approval_events.append((run_id, step_id, decision, payload))


class FakeSecurity:
    def __init__(self):
        self.calls = []

    def get_profile(self, name):
        return name

    def validate_command(self, command, profile):
        self.calls.append(("shell", command, profile))

    def validate_path(self, path, profile, write=False):
        self.calls.append(("path", path, profile, write))

    def validate_url(self, url, profile):
        self.calls.append(("url", url, profile))

    def validate_git_command(self, command, profile):
        self.calls.append(("git", command, profile))


class FakeExecutor:
    def __init__(self):
        self.calls = []

    async def execute_step(self, step, context):
        self.calls.append(step.get("tool"))
        return {
            "id": step.get("id"),
            "title": step.get("title"),
            "tool": step.get("tool"),
            "args": step.get("args", {}),
            "status": "success",
            "result": {"ok": True},
            "error": None,
        }


class FakeLogger:
    def error(self, *args, **kwargs):
        pass


def make_agent(run_profile, steps, *, current_profile="owner"):
    settings = Settings(
        env="test",
        execution_profile=current_profile,
        shell_enabled=True,
        git_enabled=True,
    )
    run = {
        "run_id": "run-1",
        "task": "Guarded continuation",
        "status": "awaiting_approval",
        "execution_profile": run_profile,
        "steps": [],
        "artifacts": [
            {
                "name": "run_plan",
                "content": json.dumps({"task": "Guarded continuation", "steps": steps}),
            }
        ],
    }
    agent = VelocityClawAgent.__new__(VelocityClawAgent)
    agent.settings = settings
    agent.logger = FakeLogger()
    agent.memory = FakeMemory(run)
    agent.profile_manager = ExecutionProfileManager(settings)
    agent.approvals = ApprovalManager(settings)
    agent.security = FakeSecurity()
    agent.executor = FakeExecutor()
    agent.step_guard = StepExecutionGuard(
        profile_manager=agent.profile_manager,
        security=agent.security,
        executor=agent.executor,
        profile_selector=agent._get_profile_for_tool,
        logger=agent.logger,
    )
    return agent


def shell_step(step_id):
    return {
        "id": step_id,
        "title": f"Shell {step_id}",
        "tool": "shell.run",
        "args": {"command": "pwd"},
    }


def test_resume_uses_stored_dev_profile_not_current_owner_profile():
    async def scenario():
        agent = make_agent("dev", [shell_step(1)], current_profile="owner")

        result = await agent.resume_after_approval("run-1", 1)

        assert result["status"] == "completed"
        assert agent.executor.calls == ["shell.run"]
        executed = result["executed"][0]
        assert executed["policy"] == {
            "profile": "dev",
            "mode": "approval",
            "approved": True,
        }
        assert agent.memory.statuses[-1] == ("run-1", "completed")

    asyncio.run(scenario())


def test_legacy_approval_cannot_override_stored_safe_profile_deny():
    async def scenario():
        agent = make_agent("safe", [shell_step(1)], current_profile="owner")

        result = await agent.resume_after_approval("run-1", 1)

        assert result["status"] == "failed"
        assert agent.executor.calls == []
        assert "denied by execution profile safe" in result["executed"][0]["error"]
        assert agent.memory.statuses[-1] == ("run-1", "failed")

    asyncio.run(scenario())


def test_continuation_reopens_approval_for_next_dev_shell_step():
    async def scenario():
        agent = make_agent("dev", [shell_step(1), shell_step(2)], current_profile="owner")

        result = await agent.resume_after_approval("run-1", 1)

        assert result["status"] == "awaiting_approval"
        assert result["boundary_step_id"] == 2
        assert agent.executor.calls == ["shell.run"]
        assert result["executed"][0]["id"] == 1
        assert agent.memory.statuses[-1] == ("run-1", "awaiting_approval")
        assert agent.memory.approval_events[-1][1:3] == (2, "requested")
        approval_payload = agent.memory.approval_events[-1][3]
        assert approval_payload["profile"] == "dev"
        assert approval_payload["policy_mode"] == "approval"

    asyncio.run(scenario())
