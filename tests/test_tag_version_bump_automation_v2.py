import shutil
from pathlib import Path

import pytest

from scripts.bump_version import bump_version, validate_version
from scripts.validate_package import validate_package


def copy_repo(tmp_path):
    root = tmp_path / "repo"
    shutil.copytree(Path.cwd(), root, ignore=shutil.ignore_patterns(".git", ".venv", "__pycache__", ".pytest_cache", "dist"))
    return root


def test_validate_version_accepts_semver():
    assert validate_version("1.2.3") == "1.2.3"


def test_validate_version_rejects_invalid_values():
    with pytest.raises(ValueError):
        validate_version("1.2")
    with pytest.raises(ValueError):
        validate_version("v1.2.3")


def test_bump_version_dry_run_does_not_write(tmp_path):
    root = copy_repo(tmp_path)
    old_version = (root / "VERSION").read_text(encoding="utf-8").strip()
    result = bump_version("0.3.0", root=root, dry_run=True)
    assert result["status"] == "ok"
    assert result["old_version"] == old_version
    assert result["new_version"] == "0.3.0"
    assert (root / "VERSION").read_text(encoding="utf-8").strip() == old_version


def test_bump_version_updates_all_metadata_files(tmp_path):
    root = copy_repo(tmp_path)
    result = bump_version("0.3.0", root=root)
    assert result["new_version"] == "0.3.0"
    assert (root / "VERSION").read_text(encoding="utf-8").strip() == "0.3.0"
    assert '__version__ = "0.3.0"' in (root / "velocity_claw" / "__version__.py").read_text(encoding="utf-8")
    assert 'version = "0.3.0"' in (root / "pyproject.toml").read_text(encoding="utf-8")
    validation = validate_package(root)
    assert validation["version"] == "0.3.0"
