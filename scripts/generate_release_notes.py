from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def extract_changelog_section(root: Path, version: str) -> str:
    changelog_path = root / "CHANGELOG.md"
    if not changelog_path.exists():
        return ""

    lines = changelog_path.read_text(encoding="utf-8").splitlines()
    header_pattern = re.compile(rf"^##\s+{re.escape(version)}(?:\s+-\s+.*)?$")
    start: int | None = None

    for index, line in enumerate(lines):
        if header_pattern.match(line.strip()):
            start = index + 1
            break

    if start is None:
        return ""

    section: list[str] = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        section.append(line)

    return "\n".join(section).strip()


def generate_release_notes(root: Path = ROOT) -> str:
    version = (root / "VERSION").read_text(encoding="utf-8").strip()
    deployment_doc = root / "docs" / "DEPLOYMENT.md"
    release_doc = root / "docs" / "RELEASE.md"
    pyproject = root / "pyproject.toml"
    changelog = extract_changelog_section(root, version)

    checks = {
        "deployment_guide": deployment_doc.exists(),
        "release_guide": release_doc.exists(),
        "changelog": (root / "CHANGELOG.md").exists(),
        "pyproject": pyproject.exists(),
        "systemd_deployment": (root / "deploy" / "systemd" / "velocity-claw.service").exists(),
        "docker_compose_deployment": (root / "deploy" / "docker" / "docker-compose.yml").exists(),
        "production_installer": (root / "deploy" / "install" / "install.sh").exists(),
        "build_artifact_workflow": (root / ".github" / "workflows" / "build-artifacts.yml").exists(),
        "release_workflow": (root / ".github" / "workflows" / "release.yml").exists(),
    }

    checklist = "\n".join(f"- [{'x' if ok else ' '}] {name.replace('_', ' ')}" for name, ok in checks.items())
    changes = changelog or "No matching changelog section was found for this version."

    return f"""# Velocity Claw v{version}

## Summary

Velocity Claw v{version} is a self-hosted AI dev-agent release focused on controlled execution, operator workflows, runtime resilience, deployment readiness, and reproducible release automation.

## Changes in this release

{changes}

## Release readiness checklist

{checklist}

## Operator docs

- `README.md`
- `CHANGELOG.md`
- `docs/DEPLOYMENT.md`
- `docs/RELEASE.md`

## Build artifacts

The GitHub Release includes the Python wheel, source distribution, and release validation summary. The same files are retained as GitHub Actions artifacts.
"""


def write_release_notes(root: Path = ROOT, output_path: Path | None = None) -> Path:
    output = output_path or root / "dist" / "release-notes.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(generate_release_notes(root), encoding="utf-8")
    return output


def main() -> int:
    path = write_release_notes()
    print(f"release notes written: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
