from __future__ import annotations

from typing import Any


ALLOW = "allow"
APPROVAL = "approval"
DENY = "deny"
VALID_MODES = {ALLOW, APPROVAL, DENY}

READ_TOOLS = {
    "analysis",
    "fs.read",
    "code.find_symbol",
    "code.read_symbol",
    "code.read_lines",
    "code.list_imports",
    "code.find_references",
    "code.find_routes",
    "git.inspect",
    "patch.preview",
}

PROFILE_TOOL_MODES: dict[str, dict[str, str]] = {
    "safe": {
        **{tool: ALLOW for tool in READ_TOOLS},
        "test.run": ALLOW,
        "fs.write": DENY,
        "fs.append": DENY,
        "fs.replace": DENY,
        "patch.apply": DENY,
        "shell.run": DENY,
        "git.run": DENY,
        "http.get": DENY,
        "http.post": DENY,
    },
    "dev": {
        **{tool: ALLOW for tool in READ_TOOLS},
        "test.run": ALLOW,
        "fs.write": ALLOW,
        "fs.append": ALLOW,
        "fs.replace": ALLOW,
        "patch.apply": ALLOW,
        "shell.run": APPROVAL,
        "git.run": DENY,
        "http.get": DENY,
        "http.post": DENY,
    },
    "owner": {
        **{tool: ALLOW for tool in READ_TOOLS},
        "test.run": ALLOW,
        "fs.write": ALLOW,
        "fs.append": ALLOW,
        "fs.replace": ALLOW,
        "patch.apply": ALLOW,
        "shell.run": ALLOW,
        "git.run": ALLOW,
        "http.get": ALLOW,
        "http.post": ALLOW,
    },
}


def get_tool_mode(profile_name: str, tool: str) -> str:
    profile_modes = PROFILE_TOOL_MODES.get(profile_name, PROFILE_TOOL_MODES["safe"])
    return profile_modes.get(tool, DENY)


def evaluate_tool_policy(
    *,
    profile_name: str,
    tool: str,
    approved: bool = False,
    explicit_approval: bool = False,
) -> dict[str, Any]:
    mode = get_tool_mode(profile_name, tool)
    blocked = mode == DENY
    profile_requires_approval = mode == APPROVAL
    explicit_gate = bool(explicit_approval and not blocked)
    requires_approval = bool(not approved and (profile_requires_approval or explicit_gate))
    allowed_now = bool(not blocked and not requires_approval)
    granted = not blocked

    if blocked:
        reason = f"Tool {tool} is denied by execution profile {profile_name}."
    elif requires_approval:
        source = "profile policy" if profile_requires_approval else "explicit step request"
        reason = f"Tool {tool} requires approval under {source}."
    elif approved and (profile_requires_approval or explicit_gate):
        reason = f"Tool {tool} is allowed after recorded approval."
    else:
        reason = f"Tool {tool} is allowed by execution profile {profile_name}."

    return {
        "profile": profile_name,
        "tool": tool,
        "mode": mode,
        "granted": granted,
        "allowed_now": allowed_now,
        "blocked": blocked,
        "requires_approval": requires_approval,
        "approved": bool(approved),
        "explicit_approval": bool(explicit_approval),
        "reason": reason,
    }


def profile_mode_summary(profile_name: str) -> dict[str, Any]:
    modes = PROFILE_TOOL_MODES.get(profile_name, PROFILE_TOOL_MODES["safe"])
    counts = {ALLOW: 0, APPROVAL: 0, DENY: 0}
    for mode in modes.values():
        counts[mode] = counts.get(mode, 0) + 1
    return {
        "profile": profile_name,
        "tool_modes": dict(sorted(modes.items())),
        "mode_counts": counts,
        "unknown_tool_mode": DENY,
    }
