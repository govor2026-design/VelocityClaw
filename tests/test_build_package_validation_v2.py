import shutil
from pathlib import Path

import pytest

from scripts.validate_package import validate_package


def test_validate_package_current_repo_ok():
    result = validate_package(Path.cwd())
    assert result["status"] == "ok"
    assert result["name"] == "velocity-claw"
    assert result["version"] == Path("VERSION").read_text(encoding="utf-8").strip()
    assert result["console_script"] == "cli:main"
    assert result["dependency_count"] > 0


def test_validate_package_detects_version_mismatch(tmp_path):
    root = tmp_path / "pkg"
    shutil.copytree(Path.cwd(), root, ignore=shutil.ignore_patterns(".git", ".venv", "__pycache__", ".pytest_cache"))
    (root / "VERSION").write_text("9.9.9\n", encoding="utf-8")
    with pytest.raises(ValueError, match="pyproject version does not match VERSION"):
        validate_package(root)
