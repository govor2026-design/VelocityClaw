from pathlib import Path


INSTALLER = Path("deploy/install/install.sh")
README = Path("deploy/install/README.md")


def test_installer_generates_api_key_for_placeholder():
    content = INSTALLER.read_text(encoding="utf-8")
    assert "API_KEY_PLACEHOLDER" in content
    assert "generate_api_key()" in content
    assert "secrets.token_urlsafe(48)" in content
    assert "ensure_api_key" in content
    assert "VELOCITY_CLAW_API_KEY" in content
    assert "change-this-long-random-key" in content


def test_installer_creates_dedicated_group_before_user():
    content = INSTALLER.read_text(encoding="utf-8")
    assert "ensure_group()" in content
    assert "groupadd --system" in content
    assert "useradd --system --gid" in content


def test_installer_readme_documents_api_key_handling():
    content = README.read_text(encoding="utf-8")
    assert "API key handling" in content
    assert "random key generated locally" in content
    assert "Keep `VELOCITY_CLAW_API_KEY` private" in content
    assert "shell/git execution disabled by default" in content
