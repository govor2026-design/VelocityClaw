from pathlib import Path


WORKFLOW = Path(".github/workflows/publish-release.yml")


def test_publish_release_workflow_is_manual_and_has_write_permission():
    content = WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in content
    assert "tag:" in content
    assert "prerelease:" in content
    assert "contents: write" in content


def test_publish_release_workflow_runs_validation_before_publish():
    content = WORKFLOW.read_text(encoding="utf-8")
    assert "Validate package metadata" in content
    assert "python scripts/validate_package.py" in content
    assert "Run tests" in content
    assert "pytest -q" in content
    assert "Validate release tag matches VERSION" in content
    assert "Build Python artifacts" in content
    assert "python -m build" in content
    assert "Generate release notes" in content
    assert "python scripts/generate_release_notes.py" in content
    assert content.index("Validate package metadata") < content.index("Create GitHub Release")
    assert content.index("Run tests") < content.index("Create GitHub Release")
    assert content.index("Build Python artifacts") < content.index("Create GitHub Release")


def test_publish_release_workflow_creates_github_release_with_artifacts():
    content = WORKFLOW.read_text(encoding="utf-8")
    assert "softprops/action-gh-release@v3" in content
    assert "tag_name: ${{ inputs.tag }}" in content
    assert "body_path: dist/release-notes.md" in content
    assert "files: |" in content
    assert "dist/*" in content
