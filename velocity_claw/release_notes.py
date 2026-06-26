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
    changelog = extract_changelog_section(root, version)
    checks = {
        "deployment_guide": (root / "docs" / "DEPLOYMENT.md").exists(),
        "release_guide": (root / "docs" / "RELEASE.md").exists(),
        "changelog": (root / "CHANGELOG.md").exists(),
        "pyproject": (root / "pyproject.toml").exists(),
        "systemd_deployment": (root / "deploy" / "systemd" / "velocity-claw.service").exists(),
        "docker_compose_deployment": (root / "deploy" / "docker" / "docker-compose.yml").exists(),
        "production_installer": (root / "deploy" / "install" / "install.sh").exists(),
        "build_artifact_workflow": (root / ".github" / "workflows" / "build-artifacts.yml").exists(),
        "release_workflow": (root / ".github" / "workflows" / "release.yml").exists(),
    }
    checklist = "\n".join(
        f"- [{'x' if ok else ' '}] {name.replace('_', ' ')}" for name, ok in checks.items()
    )
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
