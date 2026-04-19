from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path
from typing import Optional

from velocity_claw.config.settings import Settings
from velocity_claw.tools.fs import FileSystemTool


class TestRunnerTool:
    __test__ = False

    def __init__(self, settings: Settings):
        self.settings = settings
        self.fs = FileSystemTool(settings)
        self.workspace_root = Path(settings.workspace_root).resolve()

    def run(self, runner: str, target: Optional[str] = None, timeout: int = 120, extra_args: Optional[list[str]] = None, dry_run: bool = False) -> dict:
        extra_args = extra_args or []
        cmd = self._build_command(runner, target, extra_args)
        if dry_run:
            return {
                "runner": runner,
                "target": target,
                "code": 0,
                "status": "simulated",
                "stdout": "",
                "stderr": "",
                "duration_ms": 0,
                "summary": {"passed": 0, "failed": 0, "errors": 0, "skipped": 0},
                "command": cmd,
                "parsed_failures": [],
            }
        start = time.monotonic()
        try:
            completed = subprocess.run(
                cmd,
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=False,
            )
            duration_ms = int((time.monotonic() - start) * 1000)
            stdout = completed.stdout
            stderr = completed.stderr
            summary = self._extract_summary(stdout + "\n" + stderr)
            status = "passed" if completed.returncode == 0 and summary["failed"] == 0 and summary["errors"] == 0 else "failed"
            return {
                "runner": runner,
                "target": target,
                "code": completed.returncode,
                "status": status,
                "stdout": stdout,
                "stderr": stderr,
                "duration_ms": duration_ms,
                "summary": summary,
                "command": cmd,
                "parsed_failures": self.parse_failures(stdout + "\n" + stderr),
            }
        except subprocess.TimeoutExpired as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            return {
                "runner": runner,
                "target": target,
                "code": -1,
                "status": "timeout",
                "stdout": e.stdout or "",
                "stderr": e.stderr or "",
                "duration_ms": duration_ms,
                "summary": {"passed": 0, "failed": 0, "errors": 1, "skipped": 0},
                "command": cmd,
                "parsed_failures": [],
            }

    def _build_command(self, runner: str, target: Optional[str], extra_args: list[str]) -> list[str]:
        safe_extra = [arg for arg in extra_args if arg and arg.startswith("-")]
        if target:
            self.fs._validate_path(target)
        if runner == "pytest":
            cmd = ["pytest"]
        elif runner == "python -m pytest":
            cmd = ["python", "-m", "pytest"]
        else:
            raise ValueError(f"Unsupported runner: {runner}")
        if target:
            cmd.append(target)
        cmd.extend(safe_extra)
        return cmd

    def _extract_summary(self, output: str) -> dict:
        summary = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0}
        patterns = {
            "passed": r"(\d+) passed",
            "failed": r"(\d+) failed",
            "errors": r"(\d+) error[s]?",
            "skipped": r"(\d+) skipped",
        }
        for key, pattern in patterns.items():
            m = re.search(pattern, output)
            if m:
                summary[key] = int(m.group(1))
        return summary

    def parse_failures(self, output: str) -> list[dict]:
        failures = []
        current = None
        for line in output.splitlines():
            if line.startswith("FAILED "):
                tail = line[len("FAILED "):]
                file_line = None
                message = tail
                m = re.match(r"(.+?):(\d+):\s+(.*)", tail)
                if m:
                    file_line = (m.group(1), int(m.group(2)))
                    message = m.group(3)
                current = {
                    "failed_test_name": message.split(" - ")[0],
                    "file": file_line[0] if file_line else None,
                    "line": file_line[1] if file_line else None,
                    "assertion": message,
                    "traceback_summary": message,
                }
                failures.append(current)
            elif current and line.startswith("E       "):
                current["assertion"] = line.replace("E       ", "", 1).strip()
                current["traceback_summary"] = current["assertion"]
        return failures
