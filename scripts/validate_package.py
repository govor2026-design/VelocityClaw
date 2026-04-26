from __future__ import annotations

import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def validate_package(root: Path = ROOT) -> dict:
    pyproject_path = root / "pyproject.toml"
    version_path = root / "VERSION"
    version_module_path = root / "velocity_claw" / "__version__.py"
    if not pyproject_path.exists():
        raise ValueError("pyproject.toml missing")
    if not version_path.exists():
        raise ValueError("VERSION missing")
    if not version_module_path.exists():
        raise ValueError("velocity_claw/__version__.py missing")

    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    project = pyproject.get("project", {})
    version = project.get("version")
    version_file = version_path.read_text(encoding="utf-8").strip()
    version_module = version_module_path.read_text(encoding="utf-8")

    if version != version_file:
        raise ValueError("pyproject version does not match VERSION")
    if f'__version__ = "{version}"' not in version_module:
        raise ValueError("pyproject version does not match package __version__")

    scripts = project.get("scripts", {})
    if scripts.get("velocity-claw") != "cli:main":
        raise ValueError("velocity-claw console script missing or invalid")

    dependencies = project.get("dependencies", [])
    if not dependencies:
        raise ValueError("runtime dependencies missing")
    if any(item.startswith("pytest") for item in dependencies):
        raise ValueError("pytest must not be a runtime dependency")

    package_include = pyproject.get("tool", {}).get("setuptools", {}).get("packages", {}).get("find", {}).get("include", [])
    if "velocity_claw*" not in package_include:
        raise ValueError("velocity_claw package discovery missing")

    return {
        "status": "ok",
        "name": project.get("name"),
        "version": version,
        "console_script": scripts.get("velocity-claw"),
        "dependency_count": len(dependencies),
    }


def main() -> int:
    try:
        result = validate_package()
    except Exception as exc:
        print(f"package validation failed: {exc}", file=sys.stderr)
        return 1
    print(f"package validation ok: {result['name']} {result['version']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
