from pathlib import Path


WORKFLOW = Path(".github/workflows/release.yml")


def test_release_workflow_has_manual_dispatch_and_tag_input():
    content = WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in content
    assert "tag:" in content
    assert "Release tag" in content


def test_release_workflow_runs_required_validation_gates():
    content = WORKFLOW.read_text(encoding="utf-8")
    assert "Validate package metadata" in content
    assert "python scripts/validate_package.py" in content
    assert "Run tests" in content
    assert "pytest -q" in content
    assert "Validate release tag matches VERSION" in content
    assert "EXPECTED_TAG=\"v${VERSION_VALUE}\"" in content


def test_release_workflow_uploads_release_summary_artifact():
    content = WORKFLOW.read_text(encoding="utf-8")
    assert "Generate release summary" in content
    assert "dist/release-summary.md" in content
    assert "actions/upload-artifact@v4" in content
    assert "release-summary" in content
