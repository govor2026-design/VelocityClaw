import asyncio
import sqlite3
from pathlib import Path

import pytest

from velocity_claw.config.settings import Settings
from velocity_claw.core.agent import VelocityClawAgent
from velocity_claw.executor.executor import Executor
from velocity_claw.failures import (
    FailureType,
    PlanningError,
    ProviderNotConfiguredError,
    ProviderRequestError,
    ProviderResponseError,
    SecurityViolationError,
    classify_failure,
)
from velocity_claw.memory import MemoryStore
from velocity_claw.models.router import ModelRouter


def make_settings(tmp_path: Path) -> Settings:
    return Settings(
        env="test",
        workspace_root=str(tmp_path),
        memory_db_path=str(tmp_path / "memory.db"),
    )


def test_failure_taxonomy_is_stable_across_provider_security_and_planning_errors():
    assert (
        classify_failure(ProviderNotConfiguredError("missing"))
        == "provider_not_configured"
    )
    assert (
        classify_failure(ProviderRequestError("offline"))
        == "provider_request_failed"
    )
    assert (
        classify_failure(ProviderResponseError("empty"))
        == "provider_response_invalid"
    )
    assert classify_failure(SecurityViolationError("blocked")) == "security_violation"
    assert (
        classify_failure(PlanningError("bad plan"))
        == "planning_failed"
    )


def test_executor_marks_unknown_tools_and_test_failures(tmp_path: Path):
    async def scenario():
        settings = make_settings(tmp_path)
        executor = Executor(ModelRouter(settings), settings=settings)

        unknown = await executor.execute_step(
            {"id": 1, "title": "Unknown", "tool": "custom.missing", "args": {}},
            {},
        )
        executor.test_runner.run = lambda *args, **kwargs: {
            "status": "failed",
            "parsed_failures": [],
        }
        tests = await executor.execute_step(
            {
                "id": 2,
                "title": "Tests",
                "tool": "test.run",
                "args": {"runner": "pytest"},
            },
            {},
        )

        assert unknown["error_type"] == FailureType.TOOL_NOT_FOUND.value
        assert tests["error_type"] == FailureType.TEST_FAILED.value
        await executor.router.close()

    asyncio.run(scenario())


def test_existing_steps_table_is_migrated_and_error_type_is_persisted(tmp_path: Path):
    settings = make_settings(tmp_path)
    with sqlite3.connect(settings.memory_db_path) as conn:
        conn.execute(
            """
            CREATE TABLE runs (
                run_id TEXT PRIMARY KEY,
                task TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                completed_at DATETIME
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE steps (
                id INTEGER PRIMARY KEY,
                run_id TEXT NOT NULL,
                step_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                tool TEXT,
                args TEXT,
                status TEXT NOT NULL,
                result TEXT,
                error TEXT,
                started_at DATETIME,
                completed_at DATETIME
            )
            """
        )

    memory = MemoryStore(settings)
    run_id = memory.create_run("Classify failure")
    memory.save_step(
        run_id,
        {
            "id": 1,
            "title": "Blocked",
            "tool": "shell.run",
            "args": {},
            "status": "failed",
            "result": None,
            "error": "blocked",
            "error_type": "security_violation",
        },
    )

    with sqlite3.connect(settings.memory_db_path) as conn:
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(steps)").fetchall()
        }
    loaded = memory.load_steps(run_id)[0]

    assert "error_type" in columns
    assert loaded["error_type"] == "security_violation"


def test_planning_failure_is_recorded_as_structured_failed_step(tmp_path: Path):
    async def scenario():
        agent = VelocityClawAgent(make_settings(tmp_path))

        async def fail_plan(task, context):
            raise ValueError("invalid planner payload")

        agent.planner.create_plan = fail_plan
        with pytest.raises(ValueError, match="invalid planner payload"):
            await agent.run_task("Plan this")

        run = agent.memory.get_last_failed_run()
        assert run["steps"][0]["tool"] == "planner"
        assert run["steps"][0]["error_type"] == FailureType.PLANNING_FAILED.value
        assert (
            run["forensics"]["failed_step"]["error_type"]
            == FailureType.PLANNING_FAILED.value
        )
        assert any(item["artifact_type"] == "failure" for item in run["artifacts"])
        await agent.close()

    asyncio.run(scenario())
