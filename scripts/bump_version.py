from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


def validate_version(version: str) -> str:
    value = version.strip()
    if not SEMVER_RE.match(value):
        raise ValueError("version must use semantic x.y.z format")
    return value


def replace_once(content: str, old: str, new: str) -> str:
    if old not in content:
        raise ValueError(f"target not found: {old}")
    return content.replace(old, new, 1)


def bump_version(version: str, root: Path = ROOT, dry_run: bool = False) -> dict:
    new_version = validate_version(version)
    version_path = root / "VERSION"
    version_module_path = root / "velocity_claw" / "__version__.py"
    pyproject_path = root / "pyproject.toml"

    old_version = version_path.read_text(encoding="utf-8").strip()
    version_module = version_module_path.read_text(encoding="utf-8")
    pyproject = pyproject_path.read_text(encoding="utf-8")

    updated_version_file = f"{new_version}\n"
    updated_version_module = replace_once(version_module, f'__version__ = "{old_version}"', f'__version__ = "{new_version}"')
    updated_pyproject = replace_once(pyproject, f'version = "{old_version}"', f'version = "{new_version}"')

    if not dry_run:
        version_path.write_text(updated_version_file, encoding="utf-8")
        version_module_path.write_text(updated_version_module, encoding="utf-8")
        pyproject_path.write_text(updated_pyproject, encoding="utf-8")

    return {
        "status": "ok",
        "old_version": old_version,
        "new_version": new_version,
        "dry_run": dry_run,
        "updated_files": ["VERSION", "velocity_claw/__version__.py", "pyproject.toml"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Bump Velocity Claw version metadata")
    parser.add_argument("version", help="New semantic version, for example 0.2.1")
    parser.add_argument("--dry-run", action="store_true", help="Validate changes without writing files")
    args = parser.parse_args()
    result = bump_version(args.version, dry_run=args.dry_run)
    print(f"version bump {result['old_version']} -> {result['new_version']} dry_run={result['dry_run']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
