import asyncio
from pathlib import Path

from velocity_claw.config.settings import Settings
from velocity_claw.executor.executor import Executor


class DummyRouter:
    async def route(self, task_type, prompt):
        return {"text": "ok"}


def test_dry_replace_reports_false_when_content_is_unchanged(tmp_path: Path) -> None:
    target = tmp_path / "config.txt"
    target.write_text("mode=old\n", encoding="utf-8")
    executor = Executor(
        DummyRouter(),
        settings=Settings(
            env="test",
            workspace_root=str(tmp_path),
            dry_run=True,
        ),
    )

    result = asyncio.run(
        executor.execute_step(
            {
                "id": 1,
                "title": "No-op replace",
                "tool": "fs.replace",
                "args": {
                    "path": "config.txt",
                    "old_string": "old",
                    "new_string": "old",
                },
            },
            {},
        )
    )

    assert result["status"] == "success"
    assert result["result"]["would_change"] is False
    assert target.read_text(encoding="utf-8") == "mode=old\n"
