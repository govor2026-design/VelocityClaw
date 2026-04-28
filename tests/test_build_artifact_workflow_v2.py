from pathlib import Path


WORKFLOW = Path(".github/workflows/build-artifacts.yml")


def test_build_artifact_workflow_has_manual_dispatch_and_pr_paths():
    content = WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in content
    assert "pull_request:" in content
    assert "pyproject.toml" in content
    assert "scripts/validate_package.py" in content


def test_build_artifact_workflow_validates_before_building():
    content = WORKFLOW.read_text(encoding="utf-8")
    assert "Validate package metadata" in content
    assert "python scripts/validate_package.py" in content
    assert "Run tests" in content
    assert "pytest -q" in content
    assert "Build Python artifacts" in content
    assert "python -m build" in content
    assert content.index("Validate package metadata") < content.index("Build Python artifacts")
    assert content.index("Run tests") < content.index("Build Python artifacts")


def test_build_artifact_workflow_uploads_dist_artifacts():
    content = WORKFLOW.read_text(encoding="utf-8")
    assert "actions/upload-artifact@v4" in content
    assert "python-package-artifacts" in content
    assert "path: dist/*" in content
