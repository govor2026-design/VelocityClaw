import subprocess
from typing import Dict


class GitTool:
    def run_git_command(self, command: str, cwd: str = None, timeout: int = 120) -> Dict:
        git_command = command
        if not git_command.startswith("git"):
            git_command = f"git {git_command}"
        completed = subprocess.run(
            git_command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "code": completed.returncode,
            "stdout": completed.stdout.strip(),
            "stderr": completed.stderr.strip(),
        }
