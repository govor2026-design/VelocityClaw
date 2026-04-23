import shlex
import subprocess
from pathlib import Path
from typing import Dict, List
from velocity_claw.config.settings import Settings


class GitTool:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.repo_root = Path(settings.workspace_root).resolve()
        self.safe_commands = {"status", "diff", "add", "commit", "branch", "checkout", "log", "rev-parse"}
        self.destructive_commands = {
            "reset --hard", "clean -fd", "push --force", "rebase", "rm",
            "filter-branch", "gc --prune=now"
        }
        self.blocked_flags = {"--force", "-f"}

    def validate_git_command(self, command: str) -> List[str]:
        try:
            args = shlex.split(command)
        except ValueError as e:
            raise ValueError(f"Invalid git command syntax: {e}")
        if not args or args[0] != "git":
            raise ValueError("Command must start with 'git'")
        subcommand = args[1] if len(args) > 1 else ""
        if subcommand not in self.safe_commands:
            raise ValueError(f"Git subcommand '{subcommand}' not allowed")
        full_subcommand = " ".join(args[1:])
        if any(destructive in full_subcommand for destructive in self.destructive_commands):
            raise ValueError(f"Destructive git command not allowed: {full_subcommand}")
        if any(flag in args[2:] for flag in self.blocked_flags):
            raise ValueError(f"Blocked git flag in command: {full_subcommand}")
        return args

    def validate_repo_root(self, cwd: str = None) -> Path:
        cwd_path = self.repo_root if cwd is None else Path(cwd).resolve()
        if not cwd_path.is_relative_to(self.repo_root):
            raise ValueError(f"Git CWD outside repo: {cwd_path}")
        return cwd_path

    def run_git_command(self, command: str, cwd: str = None, timeout: int = 120) -> Dict:
        if not self.settings.git_enabled:
            raise RuntimeError("Git operations disabled")
        args = self.validate_git_command(command)
        cwd_path = self.validate_repo_root(cwd)
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
            raise RuntimeError(f"Git command timed out after {timeout}s")
        except FileNotFoundError:
            raise RuntimeError("Git not found")
        return {
            "code": completed.returncode,
            "stdout": completed.stdout.strip(),
            "stderr": completed.stderr.strip(),
        }

    def inspect_repo(self, cwd: str = None, timeout: int = 30) -> Dict:
        cwd_path = self.validate_repo_root(cwd)
        branch = self.run_git_command("git rev-parse --abbrev-ref HEAD", str(cwd_path), timeout=timeout)
        status = self.run_git_command("git status --short", str(cwd_path), timeout=timeout)
        recent = self.run_git_command("git log --oneline -5", str(cwd_path), timeout=timeout)
        diff = self.run_git_command("git diff --stat", str(cwd_path), timeout=timeout)
        return {
            "branch": branch.get("stdout", ""),
            "is_clean": not bool(status.get("stdout")),
            "status_short": status.get("stdout", ""),
            "recent_commits": [line for line in recent.get("stdout", "").splitlines() if line.strip()],
            "diff_stat": diff.get("stdout", ""),
            "repo_root": str(cwd_path),
        }
