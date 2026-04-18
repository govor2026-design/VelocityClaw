import subprocess
from typing import Dict


class DockerTool:
    def run_docker_command(self, command: str, timeout: int = 120) -> Dict:
        full_cmd = f"docker {command}"
        completed = subprocess.run(
            full_cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "code": completed.returncode,
            "stdout": completed.stdout.strip(),
            "stderr": completed.stderr.strip(),
        }
