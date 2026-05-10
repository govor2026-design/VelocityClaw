from pathlib import Path


DEPLOY_ENV_FILES = [
    Path("deploy/docker/velocity-claw.env.example"),
    Path("deploy/systemd/velocity-claw.env.example"),
]


def parse_env_file(path: Path) -> dict[str, str]:
    values = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        values[key] = value
    return values


def test_deploy_env_templates_include_required_api_key():
    for env_file in DEPLOY_ENV_FILES:
        values = parse_env_file(env_file)
        assert "VELOCITY_CLAW_API_KEY" in values
        assert values["VELOCITY_CLAW_API_KEY"]


def test_deploy_env_templates_disable_shell_and_git_by_default():
    for env_file in DEPLOY_ENV_FILES:
        values = parse_env_file(env_file)
        assert values["VELOCITY_CLAW_SHELL_ENABLED"] == "false"
        assert values["VELOCITY_CLAW_GIT_ENABLED"] == "false"


def test_deploy_env_templates_use_safe_profile():
    for env_file in DEPLOY_ENV_FILES:
        values = parse_env_file(env_file)
        assert values["VELOCITY_CLAW_ENV"] == "production"
        assert values["VELOCITY_CLAW_SAFE_MODE"] == "true"
        assert values["VELOCITY_CLAW_TRUSTED_MODE"] == "false"
        assert values["VELOCITY_CLAW_EXECUTION_PROFILE"] == "safe"
