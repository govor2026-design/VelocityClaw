from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional

from velocity_claw.config.settings import Settings


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
                description="Restrictive profile for safe inspection and tightly controlled actions.",
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
                description="Development-focused profile with editing, testing, and limited shell workflows.",
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
                description="Expanded trusted profile with broader tool access and auditability.",
            ),
        }

    def get_profile(self, name: Optional[str] = None) -> ExecutionProfile:
        key = name or self.settings.execution_profile
        return self._profiles.get(key, self._profiles["safe"])

    def list_profiles(self) -> dict:
        return {name: asdict(profile) for name, profile in self._profiles.items()}

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
        }

    def is_tool_allowed(self, tool: str, profile_name: Optional[str] = None) -> bool:
        profile = self.get_profile(profile_name)
        if tool in {"fs.write", "fs.append", "fs.replace"}:
            return profile.filesystem_write
        if tool in {"patch.apply", "patch.preview"}:
            return profile.patch_engine
        if tool == "test.run":
            return profile.test_runner
        if tool == "shell.run":
            return profile.shell
        if tool in {"git.run", "git.inspect"}:
            return profile.git_write or tool == "git.inspect"
        if tool in {"http.get", "http.post"}:
            return profile.network
        return True

    def explain_tool_access(self, tool: str, profile_name: Optional[str] = None) -> dict:
        profile = self.get_profile(profile_name)
        allowed = self.is_tool_allowed(tool, profile.name)
        return {
            "profile": profile.name,
            "tool": tool,
            "allowed": allowed,
            "description": profile.description,
        }


class ApprovalManager:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.profile_manager = ExecutionProfileManager(settings)

    def requires_approval(self, step: dict, profile_name: Optional[str] = None) -> bool:
        decision = self.explain_requirement(step, profile_name)
        return decision["required"]

    def explain_requirement(self, step: dict, profile_name: Optional[str] = None) -> dict:
        profile = self.profile_manager.get_profile(profile_name)
        tool = step.get("tool")
        args = step.get("args", {})
        triggers = []
        risk_level = "low"

        if args.get("require_approval") is True:
            triggers.append("explicit_require_approval")
            risk_level = "high"

        if profile.approval_workflow:
            if profile.name == "safe" and tool in {"patch.apply", "shell.run", "git.run", "fs.write", "fs.append", "fs.replace"}:
                triggers.append("safe_profile_sensitive_write_or_exec")
                risk_level = "high"
            elif profile.name == "dev" and tool in {"git.run", "shell.run"}:
                triggers.append("dev_profile_exec_or_git_write")
                risk_level = "medium"
            elif profile.name == "owner" and tool in {"shell.run", "git.run"} and args.get("require_approval") is True:
                triggers.append("owner_profile_explicit_approval")
                risk_level = "medium"

        path = args.get("path") or args.get("cwd")
        command = args.get("command")
        summary = {
            "tool": tool,
            "path": path,
            "command": command,
        }
        required = bool(triggers)
        return {
            "required": required,
            "profile": profile.name,
            "tool": tool,
            "risk_level": risk_level if required else "low",
            "triggers": triggers,
            "summary": summary,
            "reason": self._build_reason(profile.name, tool, triggers),
        }

    def build_record(self, step: dict, reason: str | None = None, profile_name: Optional[str] = None) -> dict:
        explanation = self.explain_requirement(step, profile_name)
        if reason:
            explanation["reason"] = reason
        return {
            "required": explanation["required"],
            "reason": explanation["reason"],
            "decision": None,
            "decided_by": None,
            "decided_at": None,
            "profile": explanation["profile"],
            "tool": explanation["tool"],
            "risk_level": explanation["risk_level"],
            "triggers": explanation["triggers"],
            "summary": explanation["summary"],
        }

    def _build_reason(self, profile_name: str, tool: Optional[str], triggers: list[str]) -> str:
        if not triggers:
            return "Approval not required."
        return f"Approval required for tool {tool} under profile {profile_name}: {', '.join(triggers)}"
