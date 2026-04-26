from pathlib import Path


DOC = Path("docs/DEPLOYMENT.md")


def test_deployment_guide_mentions_all_supported_paths():
    content = DOC.read_text(encoding="utf-8")
    assert "Production installer" in content
    assert "Manual systemd" in content
    assert "Docker Compose" in content
    assert "deploy/install/install.sh" in content
    assert "deploy/systemd/velocity-claw.service" in content
    assert "deploy/docker/docker-compose.yml" in content


def test_deployment_guide_documents_safe_defaults():
    content = DOC.read_text(encoding="utf-8")
    assert "safe mode enabled" in content
    assert "trusted mode disabled" in content
    assert "execution profile: `safe`" in content
    assert "shell execution disabled" in content
    assert "/var/lib/velocity-claw" in content


def test_deployment_guide_mentions_operational_checks_and_cli():
    content = DOC.read_text(encoding="utf-8")
    assert "Operational checks" in content
    assert "/health" in content
    assert "release readiness" in content
    assert "retry context" in content
    assert "JSON output mode" in content
