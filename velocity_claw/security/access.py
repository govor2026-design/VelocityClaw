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
    DENY,
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

    def get_capability_matrix(self, profile_name: Optional[str] = None) -> dict:
        profile = self.get_profile(profile_name)
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
            "policy": profile_mode_summary(profile.name),
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
        decision = self.explain_requirement(step, profile_name)
        return bool(decision["required"])

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
        risk_level = classification.get("risk_level") or "unknown"
        if blocked:
            risk_level = "high"

        path = args.get("path") or args.get("cwd")
        command = args.get("command")
        summary = {
            "tool": tool,
            "path": path,
            "command": command,
        }
        next_step_hint = self._build_next_step_hint(tool, summary, blocked=blocked)
        operator_hint = self._build_operator_hint(required, blocked, risk_level, tool)
        recommended_action = self._build_recommended_action(required, blocked, risk_level)
        approval_label = self._build_approval_label(required, blocked, risk_level, tool)
        return {
            "required": required,
            "blocked": blocked,
            "allowed_now": policy["allowed_now"],
            "profile": profile.name,
            "tool": tool,
            "policy_mode": policy["mode"],
            "risk_level": risk_level if (required or blocked) else "low",
            "triggers": triggers,
            "summary": summary,
            "reason": policy["reason"],
            "recommended_action": recommended_action,
            "operator_hint": operator_hint,
            "next_step_hint": next_step_hint,
            "approval_label": approval_label,
        }

    def build_record(self, step: dict, reason: str | None = None, profile_name: Optional[str] = None) -> dict:
        explanation = self.explain_requirement(step, profile_name)
        if reason:
            explanation["reason"] = reason
        return {
            "required": explanation["required"],
            "blocked": explanation["blocked"],
            "allowed_now": explanation["allowed_now"],
            "reason": explanation["reason"],
            "decision": None,
            "decided_by": None,
            "decided_at": None,
            "profile": explanation["profile"],
            "tool": explanation["tool"],
            "policy_mode": explanation["policy_mode"],
            "risk_level": explanation["risk_level"],
            "triggers": explanation["triggers"],
            "summary": explanation["summary"],
            "recommended_action": explanation["recommended_action"],
            "operator_hint": explanation["operator_hint"],
            "next_step_hint": explanation["next_step_hint"],
            "approval_label": explanation["approval_label"],
        }

    def _build_recommended_action(self, required: bool, blocked: bool, risk_level: str) -> str:
        if blocked:
            return "change_profile_or_replan"
        if not required:
            return "continue"
        if risk_level == "high":
            return "review_then_approve_or_reject"
        return "quick_review"

    def _build_operator_hint(self, required: bool, blocked: bool, risk_level: str, tool: Optional[str]) -> str:
        if blocked:
            return f"{tool} is hard denied by this profile; approval cannot override the policy."
        if not required:
            return "No operator action required."
        if risk_level == "high":
            return f"High-risk approval for {tool}. Review path/command details before approving."
        return f"Review {tool} before continuing."

    def _build_next_step_hint(self, tool: Optional[str], summary: dict, *, blocked: bool = False) -> str:
        if blocked:
            return "Replan with an allowed tool or switch to an explicitly authorized profile."
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
