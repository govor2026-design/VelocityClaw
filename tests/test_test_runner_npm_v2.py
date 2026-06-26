import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from velocity_claw.config.settings import Settings
from velocity_claw.executor.executor import Executor
from velocity_claw.tools.test_runner import TestRunnerTool


def make_runner(tmp_path: Path) -> TestRunnerTool:
    return TestRunnerTool(
        Settings(
            env="test",
            workspace_root=str(tmp_path),
            command_timeout=30,
        )
    )


def test_npm_command_uses_shell_free_allowlisted_arguments(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "widget.test.js").write_text("test('ok', () => {});", encoding="utf-8")
    runner = make_runner(tmp_path)

    command = runner._build_command(
        "npm test",
        "src/widget.test.js",
        ["--runInBand", "--maxWorkers=2", "--dangerous", "value"],
    )

    assert command == [
        "npm",
        "test",
        "--",
        "src/widget.test.js",
        "--runInBand",
        "--maxWorkers=2",
    ]


def test_npm_target_and_cwd_stay_inside_workspace(tmp_path: Path):
    package = tmp_path / "frontend"
    package.mkdir()
    (package / "package.json").write_text("{}", encoding="utf-8")
    runner = make_runner(tmp_path)

    result = runner.run("npm test", cwd="frontend", dry_run=True)

    assert result["status"] == "simulated"
    assert result["cwd"] == str(package.resolve())
    assert result["command"] == ["npm", "test"]

    with pytest.raises(ValueError, match="outside workspace"):
        runner.run("npm test", cwd="../outside", dry_run=True)


def test_npm_jest_output_is_structured(tmp_path: Path):
    runner = make_runner(tmp_path)
    output = """
FAIL src/widget.test.js
  ● widget › renders value

    Expected: 2
    Received: 1

      at Object.<anonymous> (src/widget.test.js:12:5)

Tests:       1 failed, 2 passed, 1 skipped, 4 total
"""
    completed = SimpleNamespace(returncode=1, stdout=output, stderr="")

    with patch("velocity_claw.tools.test_runner.subprocess.run", return_value=completed) as run_mock:
        result = runner.run("npm test", timeout=10)

    assert result["status"] == "failed"
    assert result["summary"]["collected"] == 4
    assert result["summary"]["failed"] == 1
    assert result["summary"]["passed"] == 2
    assert result["summary"]["skipped"] == 1
    assert result["parsed_failures"] == [
        {
            "failed_test_name": "widget › renders value",
            "nodeid": "widget › renders value",
            "file": "src/widget.test.js",
            "line": 12,
            "assertion": "Expected: 2 Received: 1",
            "traceback_summary": "Expected: 2 Received: 1",
            "kind": "failed",
        }
    ]
    assert run_mock.call_args.kwargs["shell"] is False
    assert run_mock.call_args.kwargs["cwd"] == tmp_path.resolve()
    assert run_mock.call_args.kwargs["timeout"] == 10


def test_missing_npm_binary_returns_structured_runner_error(tmp_path: Path):
    runner = make_runner(tmp_path)

    with patch(
        "velocity_claw.tools.test_runner.subprocess.run",
        side_effect=FileNotFoundError("npm not found"),
    ):
        result = runner.run("npm test", timeout=5)

    assert result["status"] == "runner_unavailable"
    assert result["code"] == -127
    assert result["summary"]["errors"] == 1
    assert "npm not found" in result["stderr"]


def test_timeout_is_bounded_by_runtime_setting(tmp_path: Path):
    runner = make_runner(tmp_path)

    with pytest.raises(ValueError, match="between 1 and 30"):
        runner.run("pytest", timeout=31, dry_run=True)
    with pytest.raises(ValueError, match="between 1 and 30"):
        runner.run("pytest", timeout=0, dry_run=True)


def test_pytest_targeted_selectors_are_preserved(tmp_path: Path):
    test_file = tmp_path / "test_sample.py"
    test_file.write_text("def test_value():\n    assert True\n", encoding="utf-8")
    runner = make_runner(tmp_path)

    command = runner._build_command(
        "python -m pytest",
        None,
        ["-q"],
        keyword="value",
        marker="unit",
        nodeid="test_sample.py::test_value",
    )

    assert command == [
        "python",
        "-m",
        "pytest",
        "test_sample.py::test_value",
        "-k",
        "value",
        "-m",
        "unit",
        "-q",
    ]


def test_executor_marks_failed_test_result_as_failed_step(tmp_path: Path):
    settings = Settings(env="test", workspace_root=str(tmp_path), command_timeout=30)
    executor = Executor(router=object(), settings=settings)
    captured = {}

    class FakeRunner:
        def run(self, runner, **kwargs):
            captured["runner"] = runner
            captured.update(kwargs)
            return {
                "runner": runner,
                "status": "failed",
                "code": 1,
                "stdout": "",
                "stderr": "",
                "summary": {"failed": 1},
                "parsed_failures": [{"nodeid": "test_sample.py::test_value"}],
            }

    executor.test_runner = FakeRunner()
    step = {
        "id": 1,
        "title": "Run targeted test",
        "tool": "test.run",
        "args": {
            "runner": "pytest",
            "nodeid": "test_sample.py::test_value",
            "keyword": "value",
            "marker": "unit",
            "cwd": ".",
            "timeout": 15,
        },
    }

    result = asyncio.run(executor.execute_step(step, {}))

    assert result["status"] == "failed"
    assert result["error"] == "test_run_failed"
    assert result["result"]["parsed_failures"][0]["nodeid"] == "test_sample.py::test_value"
    assert captured["nodeid"] == "test_sample.py::test_value"
    assert captured["keyword"] == "value"
    assert captured["marker"] == "unit"
    assert captured["cwd"] == "."
    assert captured["timeout"] == 15
