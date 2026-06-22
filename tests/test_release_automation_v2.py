from pathlib import Path

from scripts.generate_release_notes import extract_changelog_section, generate_release_notes


RELEASE_WORKFLOW = Path(".github/workflows/release.yml")
RELEASE_AUTOMATION_DOC = Path("docs/RELEASE_AUTOMATION.md")


def test_release_workflow_publishes_version_changes_idempotently():
    content = RELEASE_WORKFLOW.read_text(encoding="utf-8")

    required = [
        "push:",
        "workflow_dispatch:",
        "- VERSION",
        "contents: write",
        "pip-audit -r requirements.txt",
        "python -m build",
        "python scripts/generate_release_notes.py",
        'gh release view "${TAG_VALUE}"',
        'gh release create "${TAG_VALUE}"',
        'gh release edit "${TAG_VALUE}"',
        'gh release upload "${TAG_VALUE}"',
        "--clobber",
        "dist/*.whl",
        "dist/*.tar.gz",
        "--notes-file dist/release-notes.md",
    ]

    for value in required:
        assert value in content


def test_release_workflow_validates_tag_against_version():
    content = RELEASE_WORKFLOW.read_text(encoding="utf-8")

    assert 'EXPECTED_TAG="v${VERSION_VALUE}"' in content
    assert "does not match VERSION" in content
    assert 'echo "version=${VERSION_VALUE}"' in content
    assert 'echo "tag=${EXPECTED_TAG}"' in content


def test_release_automation_documentation_covers_gates_and_repair_runs():
    content = RELEASE_AUTOMATION_DOC.read_text(encoding="utf-8")

    required = [
        "VERSION",
        "velocity_claw/__version__.py",
        "pyproject.toml",
        "dependency",
        "CHANGELOG.md",
        "contents: write",
        "existing version",
        "manual",
    ]
    for value in required:
        assert value in content


def _create_release_fixture(root: Path) -> None:
    (root / "VERSION").write_text("1.2.3\n", encoding="utf-8")
    (root / "CHANGELOG.md").write_text(
        """# Changelog

## 1.2.3 - 2026-06-22

### Added

- Current release feature.

### Fixed

- Current release fix.

## 1.2.2 - 2026-06-01

### Added

- Previous release feature.
""",
        encoding="utf-8",
    )
    (root / "pyproject.toml").write_text('[project]\nversion = "1.2.3"\n', encoding="utf-8")

    for path in [
        "docs/DEPLOYMENT.md",
        "docs/RELEASE.md",
        "deploy/systemd/velocity-claw.service",
        "deploy/docker/docker-compose.yml",
        "deploy/install/install.sh",
        ".github/workflows/build-artifacts.yml",
        ".github/workflows/release.yml",
    ]:
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("fixture\n", encoding="utf-8")


def test_release_notes_include_only_current_changelog_section(tmp_path: Path):
    _create_release_fixture(tmp_path)

    section = extract_changelog_section(tmp_path, "1.2.3")
    notes = generate_release_notes(tmp_path)

    assert "Current release feature." in section
    assert "Current release fix." in section
    assert "Previous release feature." not in section
    assert "# Velocity Claw v1.2.3" in notes
    assert "## Changes in this release" in notes
    assert "Current release feature." in notes
    assert "Current release fix." in notes
    assert "Previous release feature." not in notes


def test_release_notes_report_missing_version_section(tmp_path: Path):
    _create_release_fixture(tmp_path)
    (tmp_path / "VERSION").write_text("9.9.9\n", encoding="utf-8")

    notes = generate_release_notes(tmp_path)

    assert "No matching changelog section was found for this version." in notes
