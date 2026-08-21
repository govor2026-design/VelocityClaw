import ast
from datetime import datetime, timedelta
from pathlib import Path

from velocity_claw.timestamps import utc_now_iso


def test_utc_now_iso_returns_timezone_aware_utc_value():
    timestamp = datetime.fromisoformat(utc_now_iso())

    assert timestamp.tzinfo is not None
    assert timestamp.utcoffset() == timedelta(0)


def test_runtime_does_not_call_datetime_now_without_timezone():
    failures: list[str] = []
    for path in sorted(Path("velocity_claw").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            function = node.func
            if not (
                isinstance(function, ast.Attribute)
                and function.attr == "now"
                and isinstance(function.value, ast.Name)
                and function.value.id == "datetime"
            ):
                continue
            if node.args or any(keyword.arg == "tz" for keyword in node.keywords):
                continue
            failures.append(f"{path}:{node.lineno}")

    assert not failures, "Naive datetime.now() calls: " + ", ".join(failures)
