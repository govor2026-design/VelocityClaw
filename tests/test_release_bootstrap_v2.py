from pathlib import Path


WORKFLOW = Path(".github/workflows/release.yml")
BOOTSTRAP_DOC = Path("docs/RELEASE_BOOTSTRAP.md")


def test_release_workflow_uses_environment_for_manual_tag_input():
    content = WORKFLOW.read_text(encoding="utf-8")

    assert "MANUAL_TAG: ${{ inputs.tag }}" in content
    assert 'REQUESTED_TAG="${MANUAL_TAG}"' in content
    assert 'REQUESTED_TAG="${{ inputs.tag }}"' not in content


def test_release_bootstrap_is_documented():
    content = BOOTSTRAP_DOC.read_text(encoding="utf-8")

    assert "first merge" in content
    assert "default branch" in content
    assert "subsequent change" in content
