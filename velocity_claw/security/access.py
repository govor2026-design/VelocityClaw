from __future__ import annotations

from dataclasses import dataclass
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


class ExecutionProfileManager:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._profiles = {
            "safe": ExecutionProfile("safe", filesystem_write=False, patch_engine=False, test_runner=True, shell=False, git_write=False, network=False, approval_workflow=True),
            "dev": ExecutionProfile("dev", filesystem_write=True, patch_engine=True, test_runner=True, shell=True, git_write=False, network=False, approval_workflow=True),
            "owner": ExecutionProfile("owner", filesystem_write=True, patch_engine=True, test_runner=True, shell=True, git_write=True, network=True, approval_workflow=True),
        }

    def get_profile(self, name: Optional[str] = None) -> ExecutionProfile:
        key = name or self.settings.execution_profile
        return self._profiles.get(key, self._profiles["safe"])

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
        if tool == "git.run":
            return profile.git_write
        if tool in {"http.get", "http.post"}:
            return profile.network
        return True


class ApprovalManager:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.profile_manager = ExecutionProfileManager(settings)

    def requires_approval(self, step: dict, profile_name: Optional[str] = None) -> bool:
        profile = self.profile_manager.get_profile(profile_name)
        tool = step.get("tool")
        if step.get("args", {}).get("require_approval") is True:
            return True
        if not profile.approval_workflow:
            return False
        if profile.name == "safe" and tool in {"patch.apply", "shell.run", "git.run", "fs.write", "fs.append", "fs.replace"}:
            return True
        if profile.name == "dev" and tool in {"git.run", "shell.run"}:
            return True
        return False

    def build_record(self, step: dict, reason: str) -> dict:
        return {
            "required": True,
            "reason": reason,
            "decision": None,
            "decided_by": None,
            "decided_at": None,
        }
