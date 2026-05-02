from pathlib import Path


def test_cli_entrypoint_uses_exception_boundary():
    content = Path("cli.py").read_text(encoding="utf-8")
    assert "from velocity_claw.core.runtime import exit_with_boundary" in content
    assert "exit_with_boundary(main, component=\"cli\")" in content
