from velocity_claw.config.settings import Settings
from velocity_claw.security.access import ApprovalManager, ExecutionProfileManager
from velocity_claw.security.profile_explain import classify_tool


def make_manager(profile="safe", *, shell_enabled=False, git_enabled=False):
    return ExecutionProfileManager(
        Settings(
            env="test",
            execution_profile=profile,
            shell_enabled=shell_enabled,
            git_enabled=git_enabled,
        )
    )


def make_approvals(profile="safe", *, shell_enabled=False, git_enabled=False):
    return ApprovalManager(
        Settings(
            env="test",
            execution_profile=profile,
            shell_enabled=shell_enabled,
            git_enabled=git_enabled,
        )
    )


def test_classify_tool_maps_known_tools_to_category_risk_and_capability():
    shell = classify_tool("shell.run")
    assert shell["category"] == "shell"
    assert shell["risk_level"] == "high"
    assert shell["capability"] == "shell"

    patch = classify_tool("patch.apply")
    assert patch["category"] == "patch"
    assert patch["risk_level"] == "medium"
    assert patch["capability"] == "patch_engine"

    preview = classify_tool("patch.preview")
    assert preview["category"] == "patch_preview"
    assert preview["risk_level"] == "low"
    assert preview["capability"] is None

    unknown = classify_tool("custom.tool")
    assert unknown["category"] == "unknown"
    assert unknown["risk_level"] == "unknown"
    assert unknown["capability"] is None


def test_safe_profile_explains_hard_denied_shell_access():
    explanation = make_manager("safe", shell_enabled=True).explain_tool_access("shell.run")

    assert explanation["profile"] == "safe"
    assert explanation["tool"] == "shell.run"
    assert explanation["allowed"] is False
    assert explanation["allowed_now"] is False
    assert explanation["blocked"] is True
    assert explanation["policy_mode"] == "deny"
    assert explanation["category"] == "shell"
    assert explanation["risk_level"] == "high"
    assert explanation["required_capability"] == "shell"
    assert "denied" in explanation["reason"]
    assert explanation["approval_hint"] == "approval_cannot_override_profile_deny"
    assert explanation["profile_capabilities"]["shell"] is False


def test_dev_profile_shell_is_approval_gated_and_git_write_is_denied():
    manager = make_manager("dev", shell_enabled=True, git_enabled=True)

    shell = manager.explain_tool_access("shell.run")
    assert shell["allowed"] is True
    assert shell["allowed_now"] is False
    assert shell["blocked"] is False
    assert shell["policy_mode"] == "approval"
    assert shell["approval_hint"] == "approval_required"

    git_write = manager.explain_tool_access("git.run")
    assert git_write["allowed"] is False
    assert git_write["blocked"] is True
    assert git_write["category"] == "git_write"
    assert git_write["required_capability"] == "git_write"
    assert git_write["risk_level"] == "high"


def test_owner_profile_allows_network_and_git_when_runtime_enabled():
    manager = make_manager("owner", shell_enabled=True, git_enabled=True)

    git_write = manager.explain_tool_access("git.run")
    network = manager.explain_tool_access("http.get")

    assert git_write["allowed"] is True
    assert git_write["allowed_now"] is True
    assert git_write["profile_capabilities"]["git_write"] is True
    assert network["allowed"] is True
    assert network["allowed_now"] is True
    assert network["category"] == "network_read"
    assert network["required_capability"] == "network"


def test_git_inspect_is_profile_granted_but_runtime_blocked_when_git_disabled():
    explanation = make_manager("safe", git_enabled=False).explain_tool_access("git.inspect")

    assert explanation["allowed"] is True
    assert explanation["allowed_now"] is False
    assert explanation["blocked"] is True
    assert explanation["category"] == "git_read"
    assert explanation["risk_level"] == "low"
    assert "GIT_ENABLED=false" in explanation["reason"]


def test_capability_matrix_exposes_modes_and_runtime_constraints():
    matrix = make_manager("dev", shell_enabled=True, git_enabled=False).get_capability_matrix()

    assert matrix["profile"] == "dev"
    assert matrix["policy"]["tool_modes"]["shell.run"] == "approval"
    assert matrix["policy"]["tool_modes"]["git.run"] == "deny"
    assert matrix["policy"]["unknown_tool_mode"] == "deny"
    assert matrix["runtime_constraints"]["shell_enabled"] is True
    assert matrix["runtime_constraints"]["git_enabled"] is False
    assert matrix["policy"]["effective_tools"]["shell.run"]["requires_approval"] is True


def test_approval_manager_does_not_offer_approval_for_hard_deny():
    decision = make_approvals("safe", shell_enabled=True).explain_requirement(
        {"tool": "shell.run", "args": {"command": "pwd"}}
    )

    assert decision["required"] is False
    assert decision["blocked"] is True
    assert decision["policy_mode"] == "deny"
    assert decision["recommended_action"] == "change_profile_or_runtime_then_replan"
    assert decision["approval_label"] == "denied:shell.run"


def test_dev_shell_requires_approval_only_when_runtime_enabled():
    step = {"tool": "shell.run", "args": {"command": "pwd"}}

    enabled = make_approvals("dev", shell_enabled=True).explain_requirement(step)
    assert enabled["required"] is True
    assert enabled["blocked"] is False
    assert enabled["triggers"] == ["dev_profile_approval_mode"]

    disabled = make_approvals("dev", shell_enabled=False).explain_requirement(step)
    assert disabled["required"] is False
    assert disabled["blocked"] is True
    assert disabled["runtime_blocked"] is True
    assert "SHELL_ENABLED=false" in disabled["reason"]


def test_owner_explicit_approval_is_still_enforced():
    decision = make_approvals("owner", shell_enabled=True).explain_requirement(
        {"tool": "shell.run", "args": {"command": "pwd", "require_approval": True}}
    )

    assert decision["required"] is True
    assert decision["blocked"] is False
    assert decision["triggers"] == ["explicit_require_approval"]
    assert decision["policy_mode"] == "allow"
