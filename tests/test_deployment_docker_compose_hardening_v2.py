from pathlib import Path


def test_docker_compose_has_safe_runtime_defaults():
    content = Path("deploy/docker/docker-compose.yml").read_text(encoding="utf-8")
    assert "restart: unless-stopped" in content
    assert "healthcheck:" in content
    assert "security_opt:" in content
    assert "no-new-privileges:true" in content
    assert "cap_drop:" in content
    assert "- ALL" in content
    assert "tmpfs:" in content
    assert "/tmp:rw,noexec,nosuid" in content


def test_docker_compose_declares_persistent_volumes():
    content = Path("deploy/docker/docker-compose.yml").read_text(encoding="utf-8")
    assert "velocity_claw_data" in content
    assert "velocity_claw_logs" in content
    assert "/var/lib/velocity-claw" in content
    assert "/var/log/velocity-claw" in content


def test_docker_env_defaults_to_safe_profile():
    content = Path("deploy/docker/velocity-claw.env.example").read_text(encoding="utf-8")
    assert "VELOCITY_CLAW_ENV=production" in content
    assert "VELOCITY_CLAW_SAFE_MODE=true" in content
    assert "VELOCITY_CLAW_TRUSTED_MODE=false" in content
    assert "VELOCITY_CLAW_EXECUTION_PROFILE=safe" in content
    assert "VELOCITY_CLAW_SHELL_ENABLED=false" in content
