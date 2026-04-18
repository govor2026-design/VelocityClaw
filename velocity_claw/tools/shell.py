import shlex
import subprocess
from pathlib import Path
from typing import Dict, List
from velocity_claw.config.settings import Settings


class ShellTool:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.workspace_root = Path(settings.workspace_root).resolve()
        self.allowed_commands = {
            "ls", "pwd", "echo", "cat", "grep", "find", "head", "tail",
            "wc", "sort", "uniq", "cut", "awk", "sed"
        }
        self.dangerous_patterns = {
            "rm", "rmdir", "del", "format", "fdisk", "mkfs", "dd", "sudo",
            "su", "chmod", "chown", "passwd", "useradd", "usermod",
            "systemctl", "service", "kill", "pkill", "reboot", "shutdown"
        }

    def validate_command(self, command: str) -> List[str]:
        try:
            args = shlex.split(command)
        except ValueError as e:
            raise ValueError(f"Invalid command syntax: {e}")
        if not args:
            raise ValueError("Empty command")
        base_cmd = args[0]
        if base_cmd not in self.allowed_commands:
            raise ValueError(f"Command '{base_cmd}' not allowed")
        for arg in args:
            if arg.lower() in self.dangerous_patterns:
                raise ValueError(f"Dangerous pattern in argument: {arg}")
        return args

    def validate_cwd(self, cwd: str = None) -> Path:
        cwd_path = self.workspace_root if cwd is None else Path(cwd).resolve()
        if not cwd_path.is_relative_to(self.workspace_root):
            raise ValueError(f"CWD outside workspace: {cwd_path}")
        return cwd_path

    def run_command(self, command: str, cwd: str = None, timeout: int = 120) -> Dict:
        args = self.validate_command(command)
        cwd_path = self.validate_cwd(cwd)
        try:
            completed = subprocess.run(
                args,
                shell=False,
                cwd=str(cwd_path),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Command timed out after {timeout}s")
        except FileNotFoundError as e:
            raise RuntimeError(f"Command not found: {e}")
        return {
            "code": completed.returncode,
            "stdout": completed.stdout.strip(),
            "stderr": completed.stderr.strip(),
        }
