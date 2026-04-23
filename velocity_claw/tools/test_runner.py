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
    _ALLOWED_EXACT_ARGS = {"-q", "-x", "-vv", "--lf", "--ff", "--disable-warnings"}
    _ALLOWED_PREFIX_ARGS = ("--maxfail=",)

    def __init__(self, settings: Settings):
        self.settings = settings
        self.fs = FileSystemTool(settings)
        self.workspace_root = Path(settings.workspace_root).resolve()

    def run(
        self,
        runner: str,
        target: Optional[str] = None,
        timeout: int = 120,
        extra_args: Optional[list[str]] = None,
        dry_run: bool = False,
        keyword: Optional[str] = None,
        marker: Optional[str] = None,
        nodeid: Optional[str] = None,
    ) -> dict:
        extra_args = extra_args or []
        cmd = self._build_command(runner, target, extra_args, keyword=keyword, marker=marker, nodeid=nodeid)
        if dry_run:
            return {
                "runner": runner,
                "target": target,
                "nodeid": nodeid,
                "keyword": keyword,
                "marker": marker,
                "code": 0,
                "status": "simulated",
                "stdout": "",
                "stderr": "",
                "duration_ms": 0,
                "summary": self._empty_summary(),
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
            combined = stdout + "\n" + stderr
            summary = self._extract_summary(combined)
            status = self._determine_status(completed.returncode, summary)
            return {
                "runner": runner,
                "target": target,
                "nodeid": nodeid,
                "keyword": keyword,
                "marker": marker,
                "code": completed.returncode,
                "status": status,
                "stdout": stdout,
                "stderr": stderr,
                "duration_ms": duration_ms,
                "summary": summary,
                "command": cmd,
                "parsed_failures": self.parse_failures(combined),
            }
        except subprocess.TimeoutExpired as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            return {
                "runner": runner,
                "target": target,
                "nodeid": nodeid,
                "keyword": keyword,
                "marker": marker,
                "code": -1,
                "status": "timeout",
                "stdout": e.stdout or "",
                "stderr": e.stderr or "",
                "duration_ms": duration_ms,
                "summary": {**self._empty_summary(), "errors": 1},
                "command": cmd,
                "parsed_failures": [],
            }

    def _build_command(
        self,
        runner: str,
        target: Optional[str],
        extra_args: list[str],
        *,
        keyword: Optional[str] = None,
        marker: Optional[str] = None,
        nodeid: Optional[str] = None,
    ) -> list[str]:
        safe_extra = [arg for arg in extra_args if self._is_allowed_extra_arg(arg)]
        if target:
            self.fs._validate_path(target)
        if nodeid:
            node_path = nodeid.split("::", 1)[0]
            self.fs._validate_path(node_path)
        if runner == "pytest":
            cmd = ["pytest"]
        elif runner == "python -m pytest":
            cmd = ["python", "-m", "pytest"]
        else:
            raise ValueError(f"Unsupported runner: {runner}")
        if target:
            cmd.append(target)
        if nodeid:
            cmd.append(nodeid)
        if keyword:
            cmd.extend(["-k", keyword])
        if marker:
            cmd.extend(["-m", marker])
        cmd.extend(safe_extra)
        return cmd

    def _is_allowed_extra_arg(self, arg: str) -> bool:
        if not arg:
            return False
        if arg in self._ALLOWED_EXACT_ARGS:
            return True
        return any(arg.startswith(prefix) for prefix in self._ALLOWED_PREFIX_ARGS)

    def _empty_summary(self) -> dict:
        return {
            "collected": 0,
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "skipped": 0,
            "xfailed": 0,
            "xpassed": 0,
        }

    def _determine_status(self, code: int, summary: dict) -> str:
        if code == 0 and summary["failed"] == 0 and summary["errors"] == 0:
            return "passed"
        if summary["failed"] > 0 or summary["errors"] > 0:
            return "failed"
        return "failed" if code != 0 else "passed"

    def _extract_summary(self, output: str) -> dict:
        summary = self._empty_summary()
        collected = re.search(r"collected\s+(\d+)\s+items?", output)
        if collected:
            summary["collected"] = int(collected.group(1))
        patterns = {
            "passed": r"(\d+) passed",
            "failed": r"(\d+) failed",
            "errors": r"(\d+) error[s]?",
            "skipped": r"(\d+) skipped",
            "xfailed": r"(\d+) xfailed",
            "xpassed": r"(\d+) xpassed",
        }
        for key, pattern in patterns.items():
            m = re.search(pattern, output)
            if m:
                summary[key] = int(m.group(1))
        if summary["collected"] == 0:
            counted = summary["passed"] + summary["failed"] + summary["errors"] + summary["skipped"] + summary["xfailed"] + summary["xpassed"]
            summary["collected"] = counted
        return summary

    def parse_failures(self, output: str) -> list[dict]:
        failures: list[dict] = []
        current: dict | None = None
        in_short_summary = False

        for raw_line in output.splitlines():
            line = raw_line.rstrip()
            stripped = line.strip()

            if stripped.startswith("short test summary info"):
                in_short_summary = True
                continue

            if stripped.startswith("FAILED "):
                current = self._parse_summary_line(stripped, kind="failed")
                failures.append(current)
                in_short_summary = True
                continue

            if stripped.startswith("ERROR "):
                current = self._parse_summary_line(stripped, kind="error")
                failures.append(current)
                in_short_summary = True
                continue

            if in_short_summary and current and stripped.startswith("E   "):
                message = stripped[4:].strip()
                current["assertion"] = message
                current["traceback_summary"] = message
                continue

            file_match = re.match(r"(.+\.py):(\d+):\s+in\s+", stripped)
            if current and file_match:
                current["file"] = file_match.group(1)
                current["line"] = int(file_match.group(2))
                continue

            if current and stripped.startswith("E       "):
                message = stripped.replace("E       ", "", 1).strip()
                current["assertion"] = message
                current["traceback_summary"] = message
                continue

        return failures

    def _parse_summary_line(self, line: str, *, kind: str) -> dict:
        tail = line[len("FAILED "):] if kind == "failed" else line[len("ERROR "):]
        parts = tail.split(" - ", 1)
        node = parts[0].strip()
        message = parts[1].strip() if len(parts) > 1 else tail
        file_name = node.split("::", 1)[0] if ".py" in node else None
        return {
            "failed_test_name": node,
            "nodeid": node,
            "file": file_name,
            "line": None,
            "assertion": message,
            "traceback_summary": message,
            "kind": kind,
        }
