import subprocess
from typing import Dict


class ShellTool:
    def run_command(self, command: str, cwd: str = None, timeout: int = 120) -> Dict:
        completed = subprocess.run(
            command,
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
