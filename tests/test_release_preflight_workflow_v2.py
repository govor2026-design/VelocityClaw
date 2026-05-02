from pathlib import Path


WORKFLOW = Path(".github/workflows/release-preflight.yml")


def test_release_preflight_workflow_is_manual_with_tag_input():
    content = WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in content
    assert "tag:" in content
    assert "Release tag to validate" in content


def test_release_preflight_workflow_runs_all_validation_gates():
    content = WORKFLOW.read_text(encoding="utf-8")
    assert "Validate package metadata" in content
    assert "python scripts/validate_package.py" in content
    assert "Run tests" in content
    assert "pytest -q" in content
    assert "Validate release tag matches VERSION" in content
    assert "Run dependency audit" in content
    assert "pip-audit -r requirements.txt" in content
    assert "Build Python artifacts" in content
    assert "python -m build" in content
    assert "Generate release notes" in content
    assert "python scripts/generate_release_notes.py" in content


def test_release_preflight_workflow_uploads_artifacts():
    content = WORKFLOW.read_text(encoding="utf-8")
    assert "Generate preflight summary" in content
    assert "dist/release-preflight-summary.md" in content
    assert "actions/upload-artifact@v4" in content
    assert "release-preflight-artifacts" in content
    assert "path: |" in content
    assert "dist/*" in content
