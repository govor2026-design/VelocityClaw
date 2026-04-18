from dataclasses import dataclass
from pathlib import Path
from typing import List
from urllib.parse import urlparse
from velocity_claw.config.settings import Settings


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

    def validate_path(self, path: str, profile: AccessProfile) -> Path:
        """Validate file path against security rules."""
        try:
            resolved = Path(path).resolve()
        except (OSError, ValueError) as e:
            raise ValueError(f"Invalid path: {e}")

        # Check path traversal
        if ".." in path or not resolved.is_absolute():
            raise ValueError(f"Path traversal detected: {path}")

        # Check workspace boundary
        if not resolved.is_relative_to(self.workspace_root):
            raise ValueError(f"Path outside workspace: {resolved}")

        # Check write permissions
        if profile.read_only and any(parent != resolved for parent in resolved.parents):
            if not resolved.exists() or resolved.stat().st_mode & 0o200 == 0:
                raise ValueError(f"Write access denied in read-only mode: {resolved}")

        return resolved

    def validate_url(self, url: str, profile: AccessProfile) -> str:
        """Validate URL against allowlist."""
        try:
            parsed = urlparse(url)
            if parsed.scheme not in ["http", "https"]:
                raise ValueError(f"Unsupported URL scheme: {parsed.scheme}")
            if not profile.network_allowlist:
                raise ValueError("Network access disabled")
            if parsed.hostname not in self.settings.allowed_hosts:
                raise ValueError(f"Host not in allowlist: {parsed.hostname}")
        except Exception as e:
            raise ValueError(f"Invalid URL: {e}")
        return url

    def validate_command(self, command: str, profile: AccessProfile) -> str:
        """Validate shell command."""
        if not self.settings.shell_enabled:
            raise ValueError("Shell commands disabled")

        dangerous_patterns = [
            "rm", "rmdir", "del", "format", "fdisk", "mkfs", "dd", "sudo",
            "su", "chmod", "chown", "passwd", "useradd", "usermod",
            "systemctl", "service", "kill", "pkill", "reboot", "shutdown"
        ]

        lower_cmd = command.lower()
        for pattern in dangerous_patterns:
            if pattern in lower_cmd:
                raise ValueError(f"Dangerous command pattern: {pattern}")

        return command

    def validate_git_command(self, command: str, profile: AccessProfile) -> str:
        """Validate git command."""
        if not self.settings.git_enabled:
            raise ValueError("Git commands disabled")

        if not profile.git_safe:
            raise ValueError("Git operations not allowed in current profile")

        destructive = ["reset --hard", "clean -fd", "push --force", "rebase", "rm"]
        lower_cmd = command.lower()
        for pattern in destructive:
            if pattern in lower_cmd:
                raise ValueError(f"Destructive git command: {pattern}")

        return command

    def get_profile(self, mode: str) -> AccessProfile:
        """Get access profile for mode."""
        if mode == "read_only":
            return AccessProfile(read_only=True)
        elif mode == "workspace_write":
            return AccessProfile(read_only=False, workspace_write=True)
        elif mode == "git_safe":
            return AccessProfile(read_only=False, workspace_write=True, git_safe=True)
        elif mode == "network_allowlist":
            return AccessProfile(read_only=False, workspace_write=True, git_safe=True, network_allowlist=True)
        else:
            return AccessProfile(read_only=True)  # Default safe
