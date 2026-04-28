from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def generate_release_notes(root: Path = ROOT) -> str:
    version = (root / "VERSION").read_text(encoding="utf-8").strip()
    deployment_doc = root / "docs" / "DEPLOYMENT.md"
    release_doc = root / "docs" / "RELEASE.md"
    pyproject = root / "pyproject.toml"

    checks = {
        "deployment_guide": deployment_doc.exists(),
        "release_guide": release_doc.exists(),
        "pyproject": pyproject.exists(),
        "systemd_deployment": (root / "deploy" / "systemd" / "velocity-claw.service").exists(),
        "docker_compose_deployment": (root / "deploy" / "docker" / "docker-compose.yml").exists(),
        "production_installer": (root / "deploy" / "install" / "install.sh").exists(),
        "build_artifact_workflow": (root / ".github" / "workflows" / "build-artifacts.yml").exists(),
        "release_workflow": (root / ".github" / "workflows" / "release.yml").exists(),
    }

    checklist = "\n".join(f"- [{'x' if ok else ' '}] {name.replace('_', ' ')}" for name, ok in checks.items())
    return f"""# Velocity Claw v{version}

## Summary

Velocity Claw v{version} is an advanced self-hosted AI dev-agent release focused on controlled execution, operator workflows, deployment readiness, package metadata, and release automation.

## Included release areas

- Agent runtime, memory, approvals, retry/replay, and reports
- API, dashboard helpers, operator CLI, and queue/metrics foundations
- Systemd deployment, Docker Compose deployment, and production installer
- Version metadata, package validation, release workflow, and build artifact workflow

## Release readiness checklist

{checklist}

## Operator docs

- `README.md`
- `docs/DEPLOYMENT.md`
- `docs/RELEASE.md`

## Build artifacts

Python package artifacts are built through the `build-artifacts` workflow and uploaded as GitHub Actions artifacts.
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
