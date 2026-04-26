from pathlib import Path


README = Path("README.md")


def test_readme_mentions_core_product_capabilities():
    content = README.read_text(encoding="utf-8")
    assert "self-hosted AI dev-agent" in content
    assert "approval workflow" in content
    assert "retry/replay" in content
    assert "operator CLI" in content
    assert "release readiness" in content


def test_readme_links_deployment_and_release_docs():
    content = README.read_text(encoding="utf-8")
    assert "docs/DEPLOYMENT.md" in content
    assert "docs/RELEASE.md" in content
    assert "deploy/install" in content
    assert "deploy/systemd" in content
    assert "deploy/docker" in content


def test_readme_documents_api_highlights_and_versioning():
    content = README.read_text(encoding="utf-8")
    assert "GET /runs/{run_id}/retry-context" in content
    assert "POST /runs/{run_id}/retry" in content
    assert "GET /providers/observability" in content
    assert "VERSION" in content
    assert "velocity_claw/__version__.py" in content
