from pathlib import Path


WORKFLOW = Path(".github/workflows/dependency-audit.yml")


def test_dependency_audit_workflow_has_manual_and_pr_triggers():
    content = WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in content
    assert "pull_request:" in content
    assert "requirements.txt" in content
    assert "pyproject.toml" in content


def test_dependency_audit_workflow_validates_package_metadata_and_runs_audit():
    content = WORKFLOW.read_text(encoding="utf-8")
    assert "Validate package metadata" in content
    assert "python scripts/validate_package.py" in content
    assert "Install audit tooling" in content
    assert "pip install pip-audit" in content
    assert "Run dependency audit" in content
    assert "pip-audit -r requirements.txt" in content


def test_dependency_audit_workflow_uploads_report_artifact():
    content = WORKFLOW.read_text(encoding="utf-8")
    assert "dist/dependency-audit.json" in content
    assert "actions/upload-artifact@v4" in content
    assert "dependency-audit-report" in content
