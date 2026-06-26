from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional

from velocity_claw.config.settings import Settings
from velocity_claw.security.profile_explain import (
    classify_tool,
    explain_tool_access as build_tool_access_explanation,
)
from velocity_claw.security.profile_policy_v2 import (
    APPROVAL,
    evaluate_tool_policy,
    get_tool_mode,
    profile_mode_summary,
)


class AccessControl:
    def __init__(self, settings: Settings):
        self.settings = settings

    def is_allowed(self, user_id: Optional[str]) -> bool:
        if not self.settings.allowed_users:
            return True
        return str(user_id) in [str(item) for item in self.settings.allowed_users]


@dataclass(frozen=True)
class ExecutionProfile:
    name: str
    filesystem_write: bool
    patch_engine: bool
    test_runner: bool
    shell: bool
    git_write: bool
    network: bool
    approval_workflow: bool
    description: str


class ExecutionProfileManager:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._profiles = {
            "safe": ExecutionProfile(
                "safe",
                filesystem_write=False,
                patch_engine=False,
                test_runner=True,
                shell=False,
                git_write=False,
                network=False,
                approval_workflow=True,
                description="Inspection-first profile. Read and test tools are allowed; mutation, shell, git write, and network tools are hard denied.",
            ),
            "dev": ExecutionProfile(
                "dev",
                filesystem_write=True,
                patch_engine=True,
                test_runner=True,
                shell=True,
                git_write=False,
                network=False,
                approval_workflow=True,
                description="Development profile. Workspace edits and tests are allowed, shell requires approval, git write and network remain denied.",
            ),
            "owner": ExecutionProfile(
                "owner",
                filesystem_write=True,
                patch_engine=True,
                test_runner=True,
                shell=True,
                git_write=True,
                network=True,
                approval_workflow=True,
                description="Owner profile. All registered tools are available; explicit approval requests remain enforceable and all actions stay audited.",
            ),
        }

    def get_profile(self, name: Optional[str] = None) -> ExecutionProfile:
        key = (name or self.settings.execution_profile or "safe").strip().lower()
        return self._profiles.get(key, self._profiles["safe"])

    def list_profiles(self) -> dict:
        profiles = {}
        for name, profile in self._profiles.items():
            payload = asdict(profile)
            payload["policy"] = profile_mode_summary(name)
            profiles[name] = payload
        return profiles

    def _runtime_block_reason(self, tool: str) -> str | None:
        if tool == "shell.run" and not self.settings.shell_enabled:
            return "Shell execution is disabled by runtime setting SHELL_ENABLED=false."
        if tool in {"git.run", "git.inspect"} and not self.settings.git_enabled:
            return "Git execution is disabled by runtime setting GIT_ENABLED=false."
        return None

    def get_capability_matrix(self, profile_name: Optional[str] = None) -> dict:
        profile = self.get_profile(profile_name)
        policy = profile_mode_summary(profile.name)
        policy["effective_tools"] = {
            tool: self.evaluate_tool(tool, profile.name)
            for tool in policy["tool_modes"]
        }
        return {
            "profile": profile.name,
            "description": profile.description,
            "capabilities": {
                "filesystem_write": profile.filesystem_write,
                "patch_engine": profile.patch_engine,
                "test_runner": profile.test_runner,
                "shell": profile.shell,
                "git_write": profile.git_write,
                "network": profile.network,
                "approval_workflow": profile.approval_workflow,
            },
            "runtime_constraints": {
                "shell_enabled": self.settings.shell_enabled,
                "git_enabled": self.settings.git_enabled,
                "dry_run": self.settings.dry_run,
                "allowed_hosts": list(self.settings.allowed_hosts),
            },
            "policy": policy,
        }

    def get_tool_mode(self, tool: str, profile_name: Optional[str] = None) -> str:
        profile = self.get_profile(profile_name)
        return get_tool_mode(profile.name, tool)

    def evaluate_tool(
        self,
        tool: str,
        profile_name: Optional[str] = None,
        *,
        approved: bool = False,
        explicit_approval: bool = False,
    ) -> dict:
        profile = self.get_profile(profile_name)
        decision = evaluate_tool_policy(
            profile_name=profile.name,
            tool=tool,
            approved=approved,
            explicit_approval=explicit_approval,
        )
        decision["profile_blocked"] = decision["blocked"]
        decision["runtime_blocked"] = False
        runtime_reason = self._runtime_block_reason(tool)
        if runtime_reason and not decision["profile_blocked"]:
            decision["blocked"] = True
            decision["runtime_blocked"] = True
            decision["requires_approval"] = False
            decision["allowed_now"] = False
            decision["reason"] = runtime_reason
        decision["classification"] = classify_tool(tool)
        return decision

    def is_tool_allowed(self, tool: str, profile_name: Optional[str] = None) -> bool:
        return bool(self.evaluate_tool(tool, profile_name)["granted"])

    def explain_tool_access(self, tool: str, profile_name: Optional[str] = None) -> dict:
        profile = self.get_profile(profile_name)
        policy = self.evaluate_tool(tool, profile.name)
        return build_tool_access_explanation(profile, tool, policy["granted"], policy=policy)


class ApprovalManager:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.profile_manager = ExecutionProfileManager(settings)

    def requires_approval(self, step: dict, profile_name: Optional[str] = None) -> bool:
        return bool(self.explain_requirement(step, profile_name)["required"])

    def explain_requirement(self, step: dict, profile_name: Optional[str] = None) -> dict:
        profile = self.profile_manager.get_profile(profile_name)
        tool = step.get("tool") or ""
        args = step.get("args", {}) or {}
        explicit = args.get("require_approval") is True
        policy = self.profile_manager.evaluate_tool(
            tool,
            profile.name,
            approved=False,
            explicit_approval=explicit,
        )
        classification = policy["classification"]
        triggers: list[str] = []
        if not policy["blocked"]:
            if policy["mode"] == APPROVAL:
                triggers.append(f"{profile.name}_profile_approval_mode")
            if explicit:
                triggers.append("explicit_require_approval")

        required = bool(policy["requires_approval"] and not policy["blocked"])
        blocked = bool(policy["blocked"])
        risk_level = "high" if blocked else classification.get("risk_level") or "unknown"
        summary = {
            "tool": tool,
            "path": args.get("path") or args.get("cwd"),
            "command": args.get("command"),
        }
        return {
            "required": required,
            "blocked": blocked,
            "profile_blocked": policy.get("profile_blocked", blocked),
            "runtime_blocked": policy.get("runtime_blocked", False),
            "allowed_now": policy["allowed_now"],
            "profile": profile.name,
            "tool": tool,
            "policy_mode": policy["mode"],
            "risk_level": risk_level if (required or blocked) else "low",
            "triggers": triggers,
            "summary": summary,
            "reason": policy["reason"],
            "recommended_action": self._build_recommended_action(required, blocked, risk_level),
            "operator_hint": self._build_operator_hint(required, blocked, risk_level, tool),
            "next_step_hint": self._build_next_step_hint(tool, summary, blocked=blocked),
            "approval_label": self._build_approval_label(required, blocked, risk_level, tool),
        }

    def build_record(self, step: dict, reason: str | None = None, profile_name: Optional[str] = None) -> dict:
        explanation = self.explain_requirement(step, profile_name)
        if reason:
            explanation["reason"] = reason
        return {
            **explanation,
            "decision": None,
            "decided_by": None,
            "decided_at": None,
        }

    def _build_recommended_action(self, required: bool, blocked: bool, risk_level: str) -> str:
        if blocked:
            return "change_profile_or_runtime_then_replan"
        if not required:
            return "continue"
        return "review_then_approve_or_reject" if risk_level == "high" else "quick_review"

    def _build_operator_hint(self, required: bool, blocked: bool, risk_level: str, tool: Optional[str]) -> str:
        if blocked:
            return f"{tool} is blocked by profile or runtime policy; approval cannot override the block."
        if not required:
            return "No operator action required."
        if risk_level == "high":
            return f"High-risk approval for {tool}. Review path/command details before approving."
        return f"Review {tool} before continuing."

    def _build_next_step_hint(self, tool: Optional[str], summary: dict, *, blocked: bool = False) -> str:
        if blocked:
            return "Replan with an allowed tool or enable an explicitly authorized profile/runtime capability."
        path = summary.get("path")
        command = summary.get("command")
        if tool == "patch.apply" and path:
            return f"If approved, patch will be applied to {path}."
        if tool == "shell.run" and command:
            return f"If approved, shell command will run: {command}."
        if tool == "git.run" and command:
            return f"If approved, git command will run: {command}."
        if path:
            return f"If approved, execution continues against {path}."
        return "If approved, the paused run will continue to the gated step."

    def _build_approval_label(self, required: bool, blocked: bool, risk_level: str, tool: Optional[str]) -> str:
        if blocked:
            return f"denied:{tool or 'unknown'}"
        if not required:
            return "not_required"
        return f"{risk_level}:{tool or 'unknown'}"
