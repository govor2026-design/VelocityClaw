import asyncio

from velocity_claw.config.settings import Settings
from velocity_claw.core.step_guard import StepExecutionGuard
from velocity_claw.security.access import ExecutionProfileManager


class FakeSecurity:
    def __init__(self, fail=False):
        self.fail = fail
        self.calls = []

    def get_profile(self, name):
        return name

    def validate_command(self, command, profile):
        self.calls.append(("shell", command, profile))
        if self.fail:
            raise ValueError("security blocked command")

    def validate_path(self, path, profile, write=False):
        self.calls.append(("path", path, profile, write))
        if self.fail:
            raise ValueError("security blocked path")

    def validate_url(self, url, profile):
        self.calls.append(("url", url, profile))
        if self.fail:
            raise ValueError("security blocked url")

    def validate_git_command(self, command, profile):
        self.calls.append(("git", command, profile))
        if self.fail:
            raise ValueError("security blocked git")


class FakeExecutor:
    def __init__(self):
        self.calls = []

    async def execute_step(self, step, context):
        self.calls.append((step, context))
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


def make_guard(profile, *, shell_enabled=True, git_enabled=True, security=None):
    settings = Settings(
        env="test",
        execution_profile=profile,
        shell_enabled=shell_enabled,
        git_enabled=git_enabled,
    )
    executor = FakeExecutor()
    guard = StepExecutionGuard(
        profile_manager=ExecutionProfileManager(settings),
        security=security or FakeSecurity(),
        executor=executor,
        profile_selector=lambda tool: "workspace_write" if tool == "shell.run" else "read_only",
        logger=FakeLogger(),
    )
    return guard, executor


def shell_step():
    return {"id": 1, "title": "Run pwd", "tool": "shell.run", "args": {"command": "pwd"}}


def test_dev_shell_stops_at_approval_boundary_before_security_or_executor():
    async def scenario():
        security = FakeSecurity()
        guard, executor = make_guard("dev", security=security)

        outcome = await guard.execute(shell_step(), {}, "dev", approved=False)

        assert outcome["state"] == "approval_required"
        assert outcome["step_result"] is None
        assert security.calls == []
        assert executor.calls == []

    asyncio.run(scenario())


def test_approved_dev_shell_still_passes_security_then_executes():
    async def scenario():
        security = FakeSecurity()
        guard, executor = make_guard("dev", security=security)

        outcome = await guard.execute(shell_step(), {"source": "resume"}, "dev", approved=True)

        assert outcome["state"] == "executed"
        assert outcome["step_result"]["status"] == "success"
        assert outcome["step_result"]["policy"] == {
            "profile": "dev",
            "mode": "approval",
            "approved": True,
        }
        assert security.calls == [("shell", "pwd", "workspace_write")]
        assert len(executor.calls) == 1

    asyncio.run(scenario())


def test_approval_cannot_override_safe_profile_hard_deny():
    async def scenario():
        security = FakeSecurity()
        guard, executor = make_guard("safe", security=security)

        outcome = await guard.execute(shell_step(), {}, "safe", approved=True)

        assert outcome["state"] == "blocked"
        assert outcome["step_result"]["status"] == "failed"
        assert "denied by execution profile safe" in outcome["step_result"]["error"]
        assert security.calls == []
        assert executor.calls == []

    asyncio.run(scenario())


def test_runtime_disable_cannot_be_overridden_by_approval():
    async def scenario():
        guard, executor = make_guard("dev", shell_enabled=False)

        outcome = await guard.execute(shell_step(), {}, "dev", approved=True)

        assert outcome["state"] == "blocked"
        assert "SHELL_ENABLED=false" in outcome["step_result"]["error"]
        assert executor.calls == []

    asyncio.run(scenario())


def test_security_failure_is_structured_and_executor_is_not_called():
    async def scenario():
        security = FakeSecurity(fail=True)
        guard, executor = make_guard("owner", security=security)

        outcome = await guard.execute(shell_step(), {}, "owner", approved=False)

        assert outcome["state"] == "security_failed"
        assert outcome["step_result"]["status"] == "failed"
        assert outcome["step_result"]["error"] == "security blocked command"
        assert executor.calls == []

    asyncio.run(scenario())
