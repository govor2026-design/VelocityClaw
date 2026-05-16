from velocity_claw.config.settings import Settings
from velocity_claw.security.access import ExecutionProfileManager
from velocity_claw.security.profile_explain import classify_tool


def make_manager(profile="safe"):
    return ExecutionProfileManager(Settings(env="test", execution_profile=profile))


def test_classify_tool_maps_known_tools_to_category_risk_and_capability():
    shell = classify_tool("shell.run")
    assert shell["category"] == "shell"
    assert shell["risk_level"] == "high"
    assert shell["capability"] == "shell"

    patch = classify_tool("patch.apply")
    assert patch["category"] == "patch"
    assert patch["risk_level"] == "medium"
    assert patch["capability"] == "patch_engine"

    unknown = classify_tool("custom.tool")
    assert unknown["category"] == "unknown"
    assert unknown["risk_level"] == "unknown"
    assert unknown["capability"] is None


def test_safe_profile_explains_blocked_shell_access():
    explanation = make_manager("safe").explain_tool_access("shell.run")

    assert explanation["profile"] == "safe"
    assert explanation["tool"] == "shell.run"
    assert explanation["allowed"] is False
    assert explanation["category"] == "shell"
    assert explanation["risk_level"] == "high"
    assert explanation["required_capability"] == "shell"
    assert "does not grant" in explanation["reason"]
    assert explanation["approval_hint"] == "approval_required_or_strongly_recommended"
    assert explanation["profile_capabilities"]["shell"] is False


def test_dev_profile_allows_shell_but_blocks_git_write():
    manager = make_manager("dev")

    shell = manager.explain_tool_access("shell.run")
    assert shell["allowed"] is True
    assert shell["profile_capabilities"]["shell"] is True

    git_write = manager.explain_tool_access("git.run")
    assert git_write["allowed"] is False
    assert git_write["category"] == "git_write"
    assert git_write["required_capability"] == "git_write"
    assert git_write["risk_level"] == "high"


def test_owner_profile_allows_network_and_git_write():
    manager = make_manager("owner")

    git_write = manager.explain_tool_access("git.run")
    network = manager.explain_tool_access("http.get")

    assert git_write["allowed"] is True
    assert git_write["profile_capabilities"]["git_write"] is True
    assert network["allowed"] is True
    assert network["category"] == "network"
    assert network["required_capability"] == "network"


def test_git_inspect_remains_low_risk_read_for_safe_profile():
    explanation = make_manager("safe").explain_tool_access("git.inspect")

    assert explanation["allowed"] is True
    assert explanation["category"] == "git_read"
    assert explanation["risk_level"] == "low"
    assert explanation["required_capability"] is None
