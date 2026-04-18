from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from velocity_claw.config.settings import Settings


class SecurityViolationError(ValueError):
    """Raised when an action violates agent security policy."""


@dataclass
class AccessProfile:
    read_only: bool = False
    workspace_write: bool = False
    git_safe: bool = False
    network_allowlist: bool = False


class SecurityManager:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.workspace_root = Path(settings.workspace_root).resolve()
        self.system_roots = [Path('/etc'), Path('/bin'), Path('/usr'), Path('/var'), Path('/root')]

    def _resolve_workspace_path(self, path: str) -> Path:
        raw = Path(path)
        candidate = raw if raw.is_absolute() else (self.workspace_root / raw)
        try:
            resolved = candidate.resolve()
        except (OSError, RuntimeError, ValueError) as e:
            raise SecurityViolationError(f"Invalid path: {e}")
        return resolved

    def validate_path(self, path: str, profile: AccessProfile, write: bool = False) -> Path:
        """Allow access only inside workspace_root, with explicit write permission."""
        resolved = self._resolve_workspace_path(path)

        if not resolved.is_relative_to(self.workspace_root):
            raise SecurityViolationError(f"Path outside workspace: {resolved}")

        if any(resolved == root or root in resolved.parents for root in self.system_roots):
            raise SecurityViolationError(f"System path blocked: {resolved}")

        if write and not profile.workspace_write:
            raise SecurityViolationError(f"Write access denied: {resolved}")

        return resolved

    def validate_url(self, url: str, profile: AccessProfile) -> str:
        try:
            parsed = urlparse(url)
        except Exception as e:
            raise SecurityViolationError(f"Invalid URL: {e}")

        if parsed.scheme not in {"http", "https"}:
            raise SecurityViolationError(f"Unsupported URL scheme: {parsed.scheme}")
        if not profile.network_allowlist:
            raise SecurityViolationError("Network access disabled")
        if parsed.hostname not in self.settings.allowed_hosts:
            raise SecurityViolationError(f"Host not in allowlist: {parsed.hostname}")
        return url

    def validate_command(self, command: str, profile: AccessProfile) -> str:
        if not self.settings.shell_enabled:
            raise SecurityViolationError("Shell commands disabled")
        if not profile.workspace_write:
            raise SecurityViolationError("Shell execution not allowed in current profile")

        dangerous_patterns = {
            "rm", "rmdir", "del", "format", "fdisk", "mkfs", "dd", "sudo",
            "su", "chmod", "chown", "passwd", "useradd", "usermod",
            "systemctl", "service", "kill", "pkill", "reboot", "shutdown"
        }
        tokens = command.lower().split()
        for token in tokens:
            if token in dangerous_patterns:
                raise SecurityViolationError(f"Dangerous command pattern: {token}")
        return command

    def validate_git_command(self, command: str, profile: AccessProfile) -> str:
        if not self.settings.git_enabled:
            raise SecurityViolationError("Git commands disabled")
        if not profile.git_safe:
            raise SecurityViolationError("Git operations not allowed in current profile")

        destructive = ["reset --hard", "clean -fd", "push --force", "rebase", "filter-branch", "gc --prune=now"]
        lower_cmd = command.lower()
        for pattern in destructive:
            if pattern in lower_cmd:
                raise SecurityViolationError(f"Destructive git command: {pattern}")
        return command

    def get_profile(self, mode: str) -> AccessProfile:
        if mode == "read_only":
            return AccessProfile(read_only=True)
        if mode == "workspace_write":
            return AccessProfile(workspace_write=True)
        if mode == "git_safe":
            return AccessProfile(workspace_write=True, git_safe=True)
        if mode == "network_allowlist":
            return AccessProfile(workspace_write=True, git_safe=True, network_allowlist=True)
        return AccessProfile(read_only=True)
