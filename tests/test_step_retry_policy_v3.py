import asyncio
import json
from pathlib import Path

import aiohttp

from velocity_claw.config.settings import Settings
from velocity_claw.core.agent import VelocityClawAgent
from velocity_claw.core.approval_continuation import continue_after_approval
from velocity_claw.core.step_guard import StepExecutionGuard
from velocity_claw.failures import FailureType, TransientToolError
from velocity_claw.security.access import ExecutionProfileManager
from velocity_claw.tools.http import HTTPTool


class Security:
    def get_profile(self, name):
        return name

    def validate_url(self, url, profile):
        return None


class Logger:
    def __init__(self):
        self.warnings = []

    def error(self, *args, **kwargs):
        return None

    def warning(self, *args, **kwargs):
        self.warnings.append(args)


class SequenceExecutor:
    def __init__(self, results):
        self.results = list(results)
        self.calls = 0

    async def execute_step(self, step, context):
        result = dict(self.results[self.calls])
        self.calls += 1
        return {
            "id": step["id"],
            "title": step["title"],
            "tool": step["tool"],
            "args": step.get("args", {}),
            **result,
        }


def make_guard(executor, *, max_retries=1):
    settings = Settings(env="test", execution_profile="owner")
    logger = Logger()
    guard = StepExecutionGuard(
        profile_manager=ExecutionProfileManager(settings),
        security=Security(),
        executor=executor,
        profile_selector=lambda tool: "network_allowlist",
        logger=logger,
        max_retries=max_retries,
        retry_backoff_ms=0,
    )
    return guard, logger


def failed_result(*, retryable=True):
    return {
        "status": "failed",
        "result": None,
        "error": "temporary failure",
        "error_type": FailureType.TOOL_TIMEOUT.value,
        "retryable": retryable,
    }


def success_result():
    return {
        "status": "success",
        "result": {"ok": True},
        "error": None,
        "error_type": None,
        "retryable": False,
    }


def test_transient_safe_step_retries_and_returns_attempt_metadata():
    async def scenario():
        executor = SequenceExecutor([failed_result(), success_result()])
        guard, logger = make_guard(executor)

        outcome = await guard.execute(
            {"id": 7, "title": "Fetch", "tool": "http.get", "args": {"url": "https://api.github.com"}},
            {},
            "owner",
        )

        assert executor.calls == 2
        assert [item["status"] for item in outcome["attempts"]] == ["failed", "success"]
        assert [item["attempt_no"] for item in outcome["attempts"]] == [1, 2]
        assert outcome["step_result"]["retry_count"] == 1
        assert len(logger.warnings) == 1

    asyncio.run(scenario())


def test_non_transient_and_side_effecting_steps_are_not_retried():
    async def scenario():
        deterministic = SequenceExecutor([failed_result(retryable=False)])
        deterministic_guard, _ = make_guard(deterministic, max_retries=3)
        await deterministic_guard.execute(
            {"id": 1, "title": "Read", "tool": "http.get", "args": {"url": "https://api.github.com"}},
            {},
            "owner",
        )

        unsafe = SequenceExecutor([failed_result()])
        unsafe_guard, _ = make_guard(unsafe, max_retries=3)
        await unsafe_guard.execute(
            {"id": 2, "title": "Post", "tool": "http.post", "args": {"url": "https://api.github.com"}},
            {},
            "owner",
        )

        assert deterministic.calls == 1
        assert unsafe.calls == 1

    asyncio.run(scenario())


def test_agent_persists_each_automatic_retry_attempt(tmp_path: Path):
    async def scenario():
        settings = Settings(
            env="test",
            execution_profile="owner",
            workspace_root=str(tmp_path),
            memory_db_path=str(tmp_path / "memory.db"),
            step_max_retries=1,
            step_retry_backoff_ms=0,
        )
        agent = VelocityClawAgent(settings)

        async def create_plan(task, context):
            return {
                "task": task,
                "steps": [
                    {
                        "id": 1,
                        "title": "Analyze",
                        "tool": "analysis",
                        "args": {"prompt": "inspect"},
                        "expected_output": "answer",
                    }
                ],
            }

        attempts = [failed_result(), success_result()]

        async def execute_step(step, context):
            return {
                "id": step["id"],
                "title": step["title"],
                "tool": step["tool"],
                "args": step["args"],
                **attempts.pop(0),
            }

        agent.planner.create_plan = create_plan
        agent.executor.execute_step = execute_step

        report = await agent.run_task("Retry safely")
        run = agent.memory.load_run(report["run_id"])

        assert report["status"] == "completed"
        assert report["steps"][0]["retry_count"] == 1
        assert [item["status"] for item in run["steps"]] == ["failed", "success"]
        assert [item["attempt_no"] for item in run["steps"]] == [1, 2]
        assert run["forensics"]["step_attempts"]["retried_steps"] == ["1"]
        await agent.close()

    asyncio.run(scenario())


def test_approval_continuation_retries_from_existing_attempt_number(tmp_path: Path):
    async def scenario():
        settings = Settings(
            env="test",
            execution_profile="owner",
            workspace_root=str(tmp_path),
            memory_db_path=str(tmp_path / "approval-memory.db"),
            step_max_retries=1,
            step_retry_backoff_ms=0,
        )
        agent = VelocityClawAgent(settings)
        step = {
            "id": 1,
            "title": "Analyze",
            "tool": "analysis",
            "args": {"prompt": "inspect"},
            "expected_output": "answer",
        }
        run_id = agent.memory.create_run("Continue safely")
        agent.memory.save_artifact(
            run_id,
            "run_plan",
            json.dumps({"steps": [step]}),
            artifact_type="plan",
        )
        agent.memory.save_step(
            run_id,
            {
                **step,
                "status": "approved",
                "result": {"decision": "approved"},
                "error": None,
                "attempt_no": 2,
                "phase": "failed_resume",
            },
        )
        attempts = [failed_result(), success_result()]

        async def execute_step(current_step, context):
            return {
                "id": current_step["id"],
                "title": current_step["title"],
                "tool": current_step["tool"],
                "args": current_step["args"],
                **attempts.pop(0),
            }

        agent.executor.execute_step = execute_step

        result = await continue_after_approval(agent, run_id, 1)
        records = agent.memory.load_run(run_id)["steps"]

        assert result["status"] == "completed"
        assert [item["attempt_no"] for item in records] == [2, 3]
        assert [item["status"] for item in records] == ["failed", "success"]
        assert records[-1]["phase"] == "approval_continuation"
        await agent.close()

    asyncio.run(scenario())


def test_retry_settings_are_loaded_from_prefixed_environment(monkeypatch):
    monkeypatch.setenv("VELOCITY_CLAW_STEP_MAX_RETRIES", "3")
    monkeypatch.setenv("VELOCITY_CLAW_STEP_RETRY_BACKOFF_MS", "125")

    settings = Settings(env="test")

    assert settings.step_max_retries == 3
    assert settings.step_retry_backoff_ms == 125


def test_http_retryability_distinguishes_temporary_and_permanent_statuses():
    unauthorized = aiohttp.ClientResponseError(
        None,
        (),
        status=401,
        message="unauthorized",
    )
    rate_limited = aiohttp.ClientResponseError(None, (), status=429, message="limited")
    unavailable = aiohttp.ClientResponseError(
        None,
        (),
        status=503,
        message="unavailable",
    )
    disconnected = aiohttp.ClientConnectionError("offline")

    assert type(HTTPTool._request_error(unauthorized)) is RuntimeError
    assert isinstance(HTTPTool._request_error(rate_limited), TransientToolError)
    assert isinstance(HTTPTool._request_error(unavailable), TransientToolError)
    assert isinstance(HTTPTool._request_error(disconnected), TransientToolError)
