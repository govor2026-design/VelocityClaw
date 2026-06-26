from types import SimpleNamespace

import pytest

from velocity_claw.executor.executor import Executor
from velocity_claw.tools.fs import FileSystemTool


def build_executor_surface(tmp_path, max_file_size=1024 * 1024):
    settings = SimpleNamespace(
        workspace_root=str(tmp_path),
        max_file_size=max_file_size,
    )
    return SimpleNamespace(
        settings=settings,
        fs=FileSystemTool(settings),
    )


def simulate(surface, tool, args):
    return Executor._simulate_file_action(surface, tool, args)


def test_dry_run_write_returns_diff_without_creating_file(tmp_path):
    surface = build_executor_surface(tmp_path)

    result = simulate(surface, "fs.write", {"path": "new.txt", "content": "hello\n"})

    assert result["status"] == "simulated"
    assert result["dry_run"] is True
    assert result["changed"] is True
    assert result["exists"] is False
    assert "+hello" in result["diff"]
    assert not (tmp_path / "new.txt").exists()


def test_dry_run_append_and_replace_do_not_modify_existing_file(tmp_path):
    target = tmp_path / "sample.txt"
    target.write_text("one\n", encoding="utf-8")
    surface = build_executor_surface(tmp_path)

    appended = simulate(surface, "fs.append", {"path": "sample.txt", "content": "two\n"})
    replaced = simulate(
        surface,
        "fs.replace",
        {"path": "sample.txt", "old_string": "one", "new_string": "first"},
    )

    assert "+two" in appended["diff"]
    assert "-one" in replaced["diff"]
    assert "+first" in replaced["diff"]
    assert target.read_text(encoding="utf-8") == "one\n"


def test_dry_run_no_op_write_has_empty_diff(tmp_path):
    target = tmp_path / "same.txt"
    target.write_text("same\n", encoding="utf-8")
    surface = build_executor_surface(tmp_path)

    result = simulate(surface, "fs.write", {"path": "same.txt", "content": "same\n"})

    assert result["changed"] is False
    assert result["diff"] == ""
    assert result["bytes_before"] == result["bytes_after"]


def test_dry_run_replace_preserves_validation(tmp_path):
    target = tmp_path / "sample.txt"
    target.write_text("one\n", encoding="utf-8")
    surface = build_executor_surface(tmp_path, max_file_size=5)

    with pytest.raises(ValueError, match="Old string not found"):
        simulate(
            surface,
            "fs.replace",
            {"path": "sample.txt", "old_string": "missing", "new_string": "x"},
        )

    with pytest.raises(ValueError, match="Content too large"):
        simulate(surface, "fs.append", {"path": "sample.txt", "content": "extra"})
