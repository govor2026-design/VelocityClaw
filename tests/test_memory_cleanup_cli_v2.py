from pathlib import Path


def test_cli_exposes_memory_cleanup_operator_command():
    content = Path("cli.py").read_text(encoding="utf-8")
    assert "--memory-cleanup" in content
    assert "--memory-retention-days" in content
    assert "--memory-keep-min-runs" in content
    assert "--memory-no-vacuum" in content
    assert "memory_cleanup_cli" in content
    assert "cleanup_retention" in content
