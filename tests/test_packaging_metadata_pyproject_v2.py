import sys
import tomllib
from pathlib import Path

from velocity_claw.__version__ import __version__


def load_pyproject():
    return tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))


def test_pyproject_version_matches_version_files():
    pyproject = load_pyproject()
    version_file = Path("VERSION").read_text(encoding="utf-8").strip()
    assert pyproject["project"]["version"] == version_file
    assert pyproject["project"]["version"] == __version__


def test_pyproject_declares_console_entrypoint():
    pyproject = load_pyproject()
    assert pyproject["project"]["scripts"]["velocity-claw"] == "cli:main"


def test_pyproject_runtime_and_dev_dependencies_are_separated():
    pyproject = load_pyproject()
    dependencies = pyproject["project"]["dependencies"]
    dev_dependencies = pyproject["project"]["optional-dependencies"]["dev"]
    assert any(item.startswith("fastapi") for item in dependencies)
    assert any(item.startswith("uvicorn") for item in dependencies)
    assert not any(item.startswith("pytest") for item in dependencies)
    assert any(item.startswith("pytest") for item in dev_dependencies)


def test_pyproject_package_discovery_includes_velocity_claw():
    pyproject = load_pyproject()
    assert "velocity_claw*" in pyproject["tool"]["setuptools"]["packages"]["find"]["include"]
