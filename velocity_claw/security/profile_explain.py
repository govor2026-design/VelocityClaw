from __future__ import annotations

from typing import Any


TOOL_CATEGORIES = {
    "analysis": "analysis",
    "fs.read": "filesystem_read",
    "fs.write": "filesystem_write",
    "fs.append": "filesystem_write",
    "fs.replace": "filesystem_write",
    "patch.preview": "patch_preview",
    "patch.apply": "patch",
    "test.run": "test",
    "shell.run": "shell",
    "git.inspect": "git_read",
    "git.run": "git_write",
    "http.get": "network_read",
    "http.post": "network_write",
    "code.find_symbol": "code_read",
    "code.read_symbol": "code_read",
    "code.read_lines": "code_read",
    "code.list_imports": "code_read",
    "code.find_references": "code_read",
    "code.find_routes": "code_read",
}

RISK_BY_CATEGORY = {
    "analysis": "low",
    "filesystem_read": "low",
    "filesystem_write": "medium",
    "patch_preview": "low",
    "patch": "medium",
    "test": "low",
    "shell": "high",
    "git_read": "low",
    "git_write": "high",
    "network_read": "medium",
    "network_write": "high",
    "code_read": "low",
    "unknown": "unknown",
}

CAPABILITY_BY_CATEGORY = {
    "analysis": None,
    "filesystem_read": None,
    "filesystem_write": "filesystem_write",
    "patch_preview": None,
    "patch": "patch_engine",
    "test": "test_runner",
    "shell": "shell",
    "git_read": None,
    "git_write": "git_write",
    "network_read": "network",
    "network_write": "network",
    "code_read": None,
    "unknown": None,
}


def classify_tool(tool: str) -> dict[str, Any]:
    category = TOOL_CATEGORIES.get(tool, "unknown")
    return {
        "tool": tool,
        "category": category,
        "risk_level": RISK_BY_CATEGORY.get(category, "unknown"),
        "capability": CAPABILITY_BY_CATEGORY.get(category),
    }


def explain_tool_access(
    profile: Any,
    tool: str,
    allowed: bool,
    *,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    classification = classify_tool(tool)
    category = classification["category"]
    capability = classification["capability"]
    profile_name = getattr(profile, "name", "unknown")
    policy = policy or {}
    mode = policy.get("mode", "allow" if allowed else "deny")

    if policy.get("blocked"):
        reason = policy.get("reason") or f"Tool is denied by profile '{profile_name}'."
        approval_hint = "approval_cannot_override_profile_deny"
    elif policy.get("requires_approval"):
        reason = policy.get("reason") or f"Tool requires approval in profile '{profile_name}'."
        approval_hint = "approval_required"
    elif allowed:
        reason = policy.get("reason") or "Tool is allowed by this execution profile."
        approval_hint = "approval_not_required"
    elif capability:
        reason = f"Tool requires capability '{capability}', which profile '{profile_name}' does not grant."
        approval_hint = "approval_cannot_override_profile_deny"
    else:
        reason = f"Tool category '{category}' is not explicitly granted by profile '{profile_name}'."
        approval_hint = "approval_cannot_override_profile_deny"

    return {
        "profile": profile_name,
        "description": getattr(profile, "description", ""),
        "tool": tool,
        "allowed": allowed,
        "allowed_now": policy.get("allowed_now", allowed),
        "blocked": policy.get("blocked", not allowed),
        "policy_mode": mode,
        "category": category,
        "risk_level": classification["risk_level"],
        "required_capability": capability,
        "reason": reason,
        "approval_hint": approval_hint,
        "profile_capabilities": {
            "filesystem_write": getattr(profile, "filesystem_write", False),
            "patch_engine": getattr(profile, "patch_engine", False),
            "test_runner": getattr(profile, "test_runner", False),
            "shell": getattr(profile, "shell", False),
            "git_write": getattr(profile, "git_write", False),
            "network": getattr(profile, "network", False),
            "approval_workflow": getattr(profile, "approval_workflow", False),
        },
    }
