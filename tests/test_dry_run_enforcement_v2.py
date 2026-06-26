import asyncio
from pathlib import Path

from velocity_claw.config.settings import Settings
from velocity_claw.executor.executor import Executor
from velocity_claw.memory import MemoryStore


class DummyRouter:
    async def route(self, task_type, prompt):
        return {"text": "ok"}


def make_executor(
    tmp_path: Path,
    *,
    dry_run: bool = True,
    shell_enabled: bool = False,
    git_enabled: bool = False,
    max_file_size: int = 1024,
):
    settings = Settings(
        env="test",
        workspace_root=str(tmp_path),
        dry_run=dry_run,
        shell_enabled=shell_enabled,
        git_enabled=git_enabled,
        max_file_size=max_file_size,
        allowed_hosts=["api.github.com"],
    )
    return Executor(DummyRouter(), settings=settings)


def run_step(executor, tool, args):
    return asyncio.run(
        executor.execute_step(
            {"id": 1, "title": f"Run {tool}", "tool": tool, "args": args},
            {},
        )
    )


def test_global_dry_run_cannot_be_disabled_by_step_argument(tmp_path: Path):
    executor = make_executor(tmp_path, dry_run=True)
    target = tmp_path / "created.txt"

    result = run_step(
        executor,
        "fs.write",
        {"path": "created.txt", "content": "hello", "dry_run": False},
    )

    assert result["status"] == "success"
    assert result["simulated"] is True
    assert result["result"]["status"] == "simulated"
    assert result["result"]["validated"] is True
    assert result["result"]["action"] == "fs.write"
    assert result["result"]["bytes_after"] == 5
    assert not target.exists()


def test_step_can_enable_dry_run_when_global_setting_is_false(tmp_path: Path):
    executor = make_executor(tmp_path, dry_run=False)

    result = run_step(
        executor,
        "fs.write",
        {"path": "step-dry.txt", "content": "safe", "dry_run": True},
    )

    assert result["simulated"] is True
    assert not (tmp_path / "step-dry.txt").exists()


def test_dry_run_keeps_workspace_and_size_validation_active(tmp_path: Path):
    executor = make_executor(tmp_path, dry_run=True, max_file_size=4)

    outside = run_step(
        executor,
        "fs.write",
        {"path": "../outside.txt", "content": "x"},
    )
    oversized = run_step(
        executor,
        "fs.write",
        {"path": "inside.txt", "content": "12345"},
    )

    assert outside["status"] == "failed"
    assert "outside workspace" in outside["error"]
    assert oversized["status"] == "failed"
    assert "Content too large" in oversized["error"]
    assert not (tmp_path / "inside.txt").exists()


def test_dry_replace_validates_source_and_does_not_modify_file(tmp_path: Path):
    target = tmp_path / "config.txt"
    target.write_text("mode=old\n", encoding="utf-8")
    executor = make_executor(tmp_path, dry_run=True)

    simulated = run_step(
        executor,
        "fs.replace",
        {"path": "config.txt", "old_string": "old", "new_string": "new"},
    )
    missing = run_step(
        executor,
        "fs.replace",
        {"path": "config.txt", "old_string": "missing", "new_string": "new"},
    )

    assert simulated["simulated"] is True
    assert simulated["result"]["would_change"] is True
    assert target.read_text(encoding="utf-8") == "mode=old\n"
    assert missing["status"] == "failed"
    assert "Old string not found" in missing["error"]


def test_shell_dry_run_validates_command_and_never_executes(tmp_path: Path):
    executor = make_executor(tmp_path, dry_run=True, shell_enabled=True)

    def fail_if_called(*args, **kwargs):
        raise AssertionError("shell subprocess must not run")

    executor.shell.run_command = fail_if_called
    simulated = run_step(
        executor,
        "shell.run",
        {"command": "pwd", "cwd": str(tmp_path)},
    )
    blocked = run_step(
        executor,
        "shell.run",
        {"command": "rm -rf .", "cwd": str(tmp_path)},
    )

    assert simulated["simulated"] is True
    assert simulated["result"]["argv"] == ["pwd"]
    assert blocked["status"] == "failed"


def test_disabled_shell_and_git_remain_disabled_in_dry_run(tmp_path: Path):
    executor = make_executor(tmp_path, dry_run=True, shell_enabled=False, git_enabled=False)

    shell_result = run_step(executor, "shell.run", {"command": "pwd"})
    git_result = run_step(executor, "git.run", {"command": "git status"})

    assert shell_result["status"] == "failed"
    assert shell_result["error"] == "Shell execution is disabled"
    assert git_result["status"] == "failed"
    assert git_result["error"] == "Git operations disabled"


def test_git_dry_run_validates_without_running_git(tmp_path: Path):
    executor = make_executor(tmp_path, dry_run=True, git_enabled=True)

    def fail_if_called(*args, **kwargs):
        raise AssertionError("git subprocess must not run")

    executor.git.run_git_command = fail_if_called
    result = run_step(
        executor,
        "git.run",
        {"command": "git status", "cwd": str(tmp_path)},
    )

    assert result["simulated"] is True
    assert result["result"]["argv"] == ["git", "status"]


def test_http_post_is_simulated_after_url_validation(tmp_path: Path):
    executor = make_executor(tmp_path, dry_run=True)

    class FailHTTP:
        async def post(self, *args, **kwargs):
            raise AssertionError("HTTP request must not be sent")

    executor.http = FailHTTP()
    result = run_step(
        executor,
        "http.post",
        {"url": "https://api.github.com/repos", "data": {"value": 1}},
    )

    assert result["simulated"] is True
    assert result["result"]["action"] == "http.post"
    assert result["result"]["payload_present"] is True


def test_patch_apply_dry_run_returns_diff_without_writing(tmp_path: Path):
    target = tmp_path / "sample.py"
    target.write_text("value = 'old'\n", encoding="utf-8")
    executor = make_executor(tmp_path, dry_run=True)

    result = run_step(
        executor,
        "patch.apply",
        {
            "patch": {
                "op": "replace_block",
                "path": "sample.py",
                "target": "old",
                "replacement": "new",
            }
        },
    )

    assert result["simulated"] is True
    assert result["result"]["preview_only"] is True
    assert result["result"]["changed"] is True
    assert "-value = 'old'" in result["result"]["diff"]
    assert target.read_text(encoding="utf-8") == "value = 'old'\n"


def test_run_report_lists_simulated_actions(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("VELOCITY_CLAW_ENV", "test")
    monkeypatch.setenv("VELOCITY_CLAW_MEMORY_DB_PATH", str(tmp_path / "memory.db"))
    memory = MemoryStore(Settings())
    run_id = memory.create_run("Dry-run report")
    memory.save_step(
        run_id,
        {
            "id": 1,
            "title": "Simulate write",
            "tool": "fs.write",
            "args": {"path": "file.txt"},
            "status": "success",
            "result": {
                "status": "simulated",
                "action": "fs.write",
                "path": "file.txt",
                "validated": True,
            },
            "error": None,
        },
    )
    memory.update_run_status(run_id, "completed")

    run = memory.load_run(run_id)

    assert run["report"]["dry_run_overview"]["enabled_for_run"] is True
    assert run["report"]["dry_run_overview"]["simulated_count"] == 1
    assert run["report"]["dry_run_overview"]["simulated_steps"][0]["action"] == "fs.write"
    assert "Dry-run simulated 1 action" in run["report"]["executive_summary"]
    assert run["forensics"]["dry_run"]["simulated_count"] == 1
