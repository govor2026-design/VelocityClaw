from pathlib import Path


INSTALLER = Path("deploy/install/install.sh")
README = Path("deploy/install/README.md")


def test_install_script_is_fail_fast_and_root_guarded():
    content = INSTALLER.read_text(encoding="utf-8")
    assert "set -euo pipefail" in content
    assert "require_root" in content
    assert "id -u" in content
    assert "This installer must run as root" in content


def test_install_script_uses_expected_production_paths():
    content = INSTALLER.read_text(encoding="utf-8")
    assert "APP_DIR=\"${APP_DIR:-/opt/velocityclaw}\"" in content
    assert "CONFIG_DIR=\"${CONFIG_DIR:-/etc/velocity-claw}\"" in content
    assert "STATE_DIR=\"${STATE_DIR:-/var/lib/velocity-claw}\"" in content
    assert "LOG_DIR=\"${LOG_DIR:-/var/log/velocity-claw}\"" in content


def test_install_script_installs_systemd_assets_and_config_permissions():
    content = INSTALLER.read_text(encoding="utf-8")
    assert "deploy/systemd/velocity-claw.service" in content
    assert "deploy/systemd/velocity-claw.tmpfiles.conf" in content
    assert "systemctl daemon-reload" in content
    assert "systemctl enable" in content
    assert "chmod 0640" in content
    assert "chown root:\"$APP_GROUP\"" in content


def test_install_readme_documents_safe_defaults():
    content = README.read_text(encoding="utf-8")
    assert "safe execution profile" in content
    assert "shell execution disabled" in content
    assert "/etc/velocity-claw/velocity-claw.env" in content
