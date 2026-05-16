from __future__ import annotations

from typing import Any


TOOL_CATEGORIES = {
    "fs.read": "filesystem_read",
    "fs.write": "filesystem_write",
    "fs.append": "filesystem_write",
    "fs.replace": "filesystem_write",
    "patch.preview": "patch",
    "patch.apply": "patch",
    "test.run": "test",
    "shell.run": "shell",
    "git.inspect": "git_read",
    "git.run": "git_write",
    "http.get": "network",
    "http.post": "network",
}

RISK_BY_CATEGORY = {
    "filesystem_read": "low",
    "filesystem_write": "medium",
    "patch": "medium",
    "test": "low",
    "shell": "high",
    "git_read": "low",
    "git_write": "high",
    "network": "medium",
    "unknown": "unknown",
}

CAPABILITY_BY_CATEGORY = {
    "filesystem_read": None,
    "filesystem_write": "filesystem_write",
    "patch": "patch_engine",
    "test": "test_runner",
    "shell": "shell",
    "git_read": None,
    "git_write": "git_write",
    "network": "network",
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


def explain_tool_access(profile: Any, tool: str, allowed: bool) -> dict[str, Any]:
    classification = classify_tool(tool)
    category = classification["category"]
    capability = classification["capability"]
    profile_name = getattr(profile, "name", "unknown")

    if allowed:
        reason = "Tool is allowed by this execution profile."
    elif capability:
        reason = f"Tool requires capability '{capability}', which profile '{profile_name}' does not grant."
    else:
        reason = f"Tool category '{category}' is not explicitly granted by profile '{profile_name}'."

    approval_hint = "approval_not_required"
    if getattr(profile, "approval_workflow", False):
        if classification["risk_level"] == "high":
            approval_hint = "approval_required_or_strongly_recommended"
        elif classification["risk_level"] == "medium":
            approval_hint = "approval_recommended_for_sensitive_changes"

    return {
        "profile": profile_name,
        "description": getattr(profile, "description", ""),
        "tool": tool,
        "allowed": allowed,
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
