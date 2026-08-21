import ast
from pathlib import Path


def test_package_sources_parse_on_minimum_supported_python():
    failures: list[str] = []
    for path in sorted(Path("velocity_claw").rglob("*.py")):
        try:
            ast.parse(
                path.read_text(encoding="utf-8"),
                filename=str(path),
                feature_version=(3, 10),
            )
        except SyntaxError as exc:
            failures.append(f"{path}:{exc.lineno}: {exc.msg}")

    assert not failures, "Python 3.10 syntax errors:\n" + "\n".join(failures)
