from pathlib import Path


def test_systemd_service_has_hardening_directives():
    content = Path("deploy/systemd/velocity-claw.service").read_text(encoding="utf-8")
    assert "User=velocityclaw" in content
    assert "EnvironmentFile=/etc/velocity-claw/velocity-claw.env" in content
    assert "ExecStart=/opt/velocityclaw/.venv/bin/python cli.py --server" in content
    assert "Restart=on-failure" in content
    assert "NoNewPrivileges=true" in content
    assert "PrivateTmp=true" in content
    assert "ProtectSystem=full" in content
    assert "ProtectHome=true" in content
    assert "CapabilityBoundingSet=" in content
    assert "SystemCallArchitectures=native" in content


def test_systemd_env_example_defaults_to_safe_profile():
    content = Path("deploy/systemd/velocity-claw.env.example").read_text(encoding="utf-8")
    assert "VELOCITY_CLAW_ENV=production" in content
    assert "VELOCITY_CLAW_SAFE_MODE=true" in content
    assert "VELOCITY_CLAW_TRUSTED_MODE=false" in content
    assert "VELOCITY_CLAW_EXECUTION_PROFILE=safe" in content
    assert "VELOCITY_CLAW_SHELL_ENABLED=false" in content


def test_systemd_tmpfiles_declares_runtime_directories():
    content = Path("deploy/systemd/velocity-claw.tmpfiles.conf").read_text(encoding="utf-8")
    assert "/var/lib/velocity-claw" in content
    assert "/var/lib/velocity-claw/workspace" in content
    assert "/var/log/velocity-claw" in content
    assert "/etc/velocity-claw" in content
