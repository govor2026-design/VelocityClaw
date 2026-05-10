from pathlib import Path

from velocity_claw.config.settings import Settings


def test_shell_and_git_are_disabled_by_default(monkeypatch):
    monkeypatch.delenv("SHELL_ENABLED", raising=False)
    monkeypatch.delenv("GIT_ENABLED", raising=False)
    monkeypatch.setenv("ENV", "test")
    settings = Settings()
    assert settings.shell_enabled is False
    assert settings.git_enabled is False


def test_env_example_keeps_destructive_tools_disabled_by_default():
    content = Path(".env.example").read_text(encoding="utf-8")
    assert "SHELL_ENABLED=false" in content
    assert "GIT_ENABLED=false" in content
    assert "SHELL_ENABLED=true" not in content
    assert "GIT_ENABLED=true" not in content


def test_readme_does_not_include_personal_windows_path():
    content = Path("README.md").read_text(encoding="utf-8")
    assert "C:\\Users\\gavar\\VelocityClaw" not in content
    assert "C:/Users/gavar/VelocityClaw" not in content
