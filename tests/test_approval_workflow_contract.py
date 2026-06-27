from pathlib import Path

import pytest

from velocity_claw.config.settings import Settings
from velocity_claw.core.agent import VelocityClawAgent


@pytest.mark.asyncio
async def test_safe_profile_pauses_before_sensitive_step_and_resumes(tmp_path: Path) -> None:
    settings = Settings(
        workspace_root=str(tmp_path),
        memory_db_path=str(tmp_path / "memory.db"),
        execution_profile="safe",
    )
    target = tmp_path / "sample.py"
    target.write_text("value = 'old'\n")
    agent = VelocityClawAgent(settings)

    async def fake_plan(task, context=None):
        return {
            "task": task,
            "steps": [
                {
                    "id": 1,
                    "title": "patch sample",
                    "tool": "patch.apply",
                    "args": {
                        "patch": {
                            "op": "replace_block",
                            "path": "sample.py",
                            "target": "old",
                            "replacement": "new",
                        }
                    },
                    "expected_output": "patched",
                }
            ],
        }

    agent.planner.create_plan = fake_plan

    paused = await agent.run_task("patch")

    assert paused["status"] == "awaiting_approval"
    assert target.read_text() == "value = 'old'\n"
    stored = agent.memory.load_run(paused["run_id"])
    assert stored["status"] == "awaiting_approval"
    assert any(artifact["name"] == "run_plan" for artifact in stored["artifacts"])

    approval = await agent.approve_step(paused["run_id"], 1, actor="qa", reason="reviewed")

    assert approval["decision"] == "approved"
    assert approval["resume"]["status"] == "completed"
    assert target.read_text() == "value = 'new'\n"
    assert agent.memory.load_run(paused["run_id"])["status"] == "completed"
