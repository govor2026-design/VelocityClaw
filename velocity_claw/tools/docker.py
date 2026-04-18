import shlex
import subprocess
from typing import Dict


ALLOWED_DOCKER_SUBCOMMANDS = {
    "ps", "images", "logs", "inspect", "stats", "top",
    "build", "run", "stop", "start", "restart", "rm",
    "pull", "push", "exec", "cp", "version", "info"
}

DANGEROUS_PATTERNS = ["--privileged", "--cap-add", "-v /", "--network host", "rm -f"]


class DockerTool:
    def validate_docker_command(self, command: str) -> list:
        try:
            args = shlex.split(command)
        except ValueError as e:
            raise ValueError(f"Invalid docker command syntax: {e}")

        if not args or args[0] != "docker":
            raise ValueError("Command must start with 'docker'")

        subcommand = args[1] if len(args) > 1 else ""
        if subcommand not in ALLOWED_DOCKER_SUBCOMMANDS:
            raise ValueError(f"Docker subcommand '{subcommand}' not allowed")

        full_cmd = " ".join(args)
        for pattern in DANGEROUS_PATTERNS:
            if pattern in full_cmd:
                raise ValueError(f"Dangerous docker pattern not allowed: {pattern}")

        return args

    def run_docker_command(self, command: str, timeout: int = 120) -> Dict:
        args = self.validate_docker_command(command)
        try:
            completed = subprocess.run(
                args,
                shell=False,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Docker command timed out after {timeout}s")
        except FileNotFoundError:
            raise RuntimeError("Docker not found")

        return {
            "code": completed.returncode,
            "stdout": completed.stdout.strip(),
            "stderr": completed.stderr.strip(),
        }
