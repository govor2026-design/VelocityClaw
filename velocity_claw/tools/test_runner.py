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

    _PYTEST_ALLOWED_EXACT_ARGS = {
        "-q",
        "-x",
        "-vv",
        "--lf",
        "--ff",
        "--disable-warnings",
        "--tb=short",
        "--tb=line",
        "--strict-markers",
    }
    _PYTEST_ALLOWED_PREFIX_ARGS = ("--maxfail=",)

    _NPM_ALLOWED_EXACT_ARGS = {
        "--runInBand",
        "--watch=false",
        "--passWithNoTests",
        "--coverage",
        "--silent",
        "--verbose",
    }
    _NPM_ALLOWED_PREFIX_ARGS = (
        "--testNamePattern=",
        "--testPathPattern=",
        "--maxWorkers=",
    )

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
        cwd: Optional[str] = None,
    ) -> dict:
        extra_args = extra_args or []
        timeout_seconds = self._normalize_timeout(timeout)
        working_directory = self._resolve_cwd(cwd)
        cmd = self._build_command(
            runner,
            target,
            extra_args,
            keyword=keyword,
            marker=marker,
            nodeid=nodeid,
        )
        base = {
            "runner": runner,
            "target": target,
            "nodeid": nodeid,
            "keyword": keyword,
            "marker": marker,
            "cwd": str(working_directory),
            "timeout_seconds": timeout_seconds,
            "command": cmd,
        }
        if dry_run:
            return {
                **base,
                "code": 0,
                "status": "simulated",
                "stdout": "",
                "stderr": "",
                "duration_ms": 0,
                "summary": self._empty_summary(),
                "parsed_failures": [],
            }

        start = time.monotonic()
        try:
            completed = subprocess.run(
                cmd,
                cwd=working_directory,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                shell=False,
            )
            duration_ms = int((time.monotonic() - start) * 1000)
            stdout = completed.stdout or ""
            stderr = completed.stderr or ""
            combined = stdout + "\n" + stderr
            summary = self._extract_summary(combined, runner)
            return {
                **base,
                "code": completed.returncode,
                "status": self._determine_status(completed.returncode, summary),
                "stdout": stdout,
                "stderr": stderr,
                "duration_ms": duration_ms,
                "summary": summary,
                "parsed_failures": self.parse_failures(combined, runner=runner),
            }
        except subprocess.TimeoutExpired as exc:
            duration_ms = int((time.monotonic() - start) * 1000)
            return {
                **base,
                "code": -1,
                "status": "timeout",
                "stdout": self._decode_process_output(exc.stdout),
                "stderr": self._decode_process_output(exc.stderr),
                "duration_ms": duration_ms,
                "summary": {**self._empty_summary(), "errors": 1},
                "parsed_failures": [],
            }
        except FileNotFoundError as exc:
            duration_ms = int((time.monotonic() - start) * 1000)
            return {
                **base,
                "code": -127,
                "status": "runner_unavailable",
                "stdout": "",
                "stderr": str(exc),
                "duration_ms": duration_ms,
                "summary": {**self._empty_summary(), "errors": 1},
                "parsed_failures": [],
            }

    @staticmethod
    def _decode_process_output(value) -> str:
        if value is None:
            return ""
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return str(value)

    def _normalize_timeout(self, timeout: int) -> int:
        try:
            value = int(timeout)
        except (TypeError, ValueError) as exc:
            raise ValueError("Test timeout must be an integer") from exc
        maximum = max(1, int(self.settings.command_timeout))
        if value < 1 or value > maximum:
            raise ValueError(f"Test timeout must be between 1 and {maximum} seconds")
        return value

    def _resolve_cwd(self, cwd: Optional[str]) -> Path:
        resolved = self.workspace_root if not cwd else self.fs._validate_path(cwd)
        if not resolved.exists():
            raise ValueError(f"Test working directory does not exist: {resolved}")
        if not resolved.is_dir():
            raise ValueError(f"Test working directory is not a directory: {resolved}")
        return resolved

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
        normalized = str(runner or "").strip().lower()
        safe_extra = [
            arg for arg in extra_args
            if self._is_allowed_extra_arg(arg, normalized)
        ]

        if normalized in {"pytest", "python -m pytest"}:
            if target:
                self.fs._validate_path(target)
            if nodeid:
                node_path = nodeid.split("::", 1)[0]
                self.fs._validate_path(node_path)
            cmd = ["pytest"] if normalized == "pytest" else ["python", "-m", "pytest"]
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

        if normalized == "npm test":
            if nodeid or marker:
                raise ValueError("nodeid and marker selectors are only supported by pytest")
            if target:
                self.fs._validate_path(target)
            npm_args = list(safe_extra)
            if keyword:
                npm_args.append(f"--testNamePattern={keyword}")
            cmd = ["npm", "test"]
            if target or npm_args:
                cmd.append("--")
            if target:
                cmd.append(target)
            cmd.extend(npm_args)
            return cmd

        raise ValueError(f"Unsupported runner: {runner}")

    def _is_allowed_extra_arg(self, arg: str, runner: str = "pytest") -> bool:
        if not arg or not isinstance(arg, str):
            return False
        if runner == "npm test":
            if arg in self._NPM_ALLOWED_EXACT_ARGS:
                return True
            return any(arg.startswith(prefix) for prefix in self._NPM_ALLOWED_PREFIX_ARGS)
        if arg in self._PYTEST_ALLOWED_EXACT_ARGS:
            return True
        return any(arg.startswith(prefix) for prefix in self._PYTEST_ALLOWED_PREFIX_ARGS)

    @staticmethod
    def _empty_summary() -> dict:
        return {
            "collected": 0,
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "skipped": 0,
            "xfailed": 0,
            "xpassed": 0,
        }

    @staticmethod
    def _determine_status(code: int, summary: dict) -> str:
        if code == 0 and summary["failed"] == 0 and summary["errors"] == 0:
            return "passed"
        return "failed"

    def _extract_summary(self, output: str, runner: str = "pytest") -> dict:
        if str(runner).strip().lower() == "npm test":
            return self._extract_npm_summary(output)
        return self._extract_pytest_summary(output)

    def _extract_pytest_summary(self, output: str) -> dict:
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
            match = re.search(pattern, output)
            if match:
                summary[key] = int(match.group(1))
        if summary["collected"] == 0:
            summary["collected"] = sum(
                summary[key]
                for key in ("passed", "failed", "errors", "skipped", "xfailed", "xpassed")
            )
        return summary

    def _extract_npm_summary(self, output: str) -> dict:
        summary = self._empty_summary()
        tests_line = next(
            (line for line in output.splitlines() if line.strip().startswith("Tests:")),
            "",
        )
        mappings = {
            "passed": r"(\d+)\s+passed",
            "failed": r"(\d+)\s+failed",
            "skipped": r"(\d+)\s+(?:skipped|pending|todo)",
            "collected": r"(\d+)\s+total",
        }
        for key, pattern in mappings.items():
            match = re.search(pattern, tests_line, flags=re.IGNORECASE)
            if match:
                summary[key] = int(match.group(1))
        if summary["collected"] == 0:
            summary["collected"] = summary["passed"] + summary["failed"] + summary["skipped"]
        return summary

    def parse_failures(self, output: str, runner: str = "pytest") -> list[dict]:
        if str(runner).strip().lower() == "npm test":
            return self._parse_jest_failures(output)
        return self._parse_pytest_failures(output)

    def _parse_pytest_failures(self, output: str) -> list[dict]:
        failures: list[dict] = []
        current: dict | None = None
        in_short_summary = False

        for raw_line in output.splitlines():
            stripped = raw_line.rstrip().strip()
            if stripped.startswith("short test summary info"):
                in_short_summary = True
                continue
            if stripped.startswith("FAILED "):
                current = self._parse_pytest_summary_line(stripped, kind="failed")
                failures.append(current)
                in_short_summary = True
                continue
            if stripped.startswith("ERROR "):
                current = self._parse_pytest_summary_line(stripped, kind="error")
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
        return failures

    @staticmethod
    def _parse_pytest_summary_line(line: str, *, kind: str) -> dict:
        tail = line[len("FAILED "):] if kind == "failed" else line[len("ERROR "):]
        parts = tail.split(" - ", 1)
        node = parts[0].strip()
        message = parts[1].strip() if len(parts) > 1 else tail
        return {
            "failed_test_name": node,
            "nodeid": node,
            "file": node.split("::", 1)[0] if ".py" in node else None,
            "line": None,
            "assertion": message,
            "traceback_summary": message,
            "kind": kind,
        }

    def _parse_jest_failures(self, output: str) -> list[dict]:
        failures: list[dict] = []
        current_file: str | None = None
        current: dict | None = None
        message_lines: list[str] = []

        def flush_message() -> None:
            nonlocal message_lines
            if current is not None and message_lines:
                message = " ".join(message_lines).strip()
                current["assertion"] = message
                current["traceback_summary"] = message
            message_lines = []

        for raw_line in output.splitlines():
            stripped = raw_line.strip()
            if stripped.startswith("FAIL "):
                flush_message()
                current_file = stripped[5:].split()[0]
                current = None
                continue
            if stripped.startswith("● "):
                flush_message()
                test_name = stripped[2:].strip()
                current = {
                    "failed_test_name": test_name,
                    "nodeid": test_name,
                    "file": current_file,
                    "line": None,
                    "assertion": test_name,
                    "traceback_summary": test_name,
                    "kind": "failed",
                }
                failures.append(current)
                continue
            if current is None:
                continue
            stack = re.search(r"(?:\(|\s)([^\s()]+\.(?:js|jsx|ts|tsx)):(\d+):(\d+)\)?$", stripped)
            if stack:
                current["file"] = stack.group(1)
                current["line"] = int(stack.group(2))
                continue
            if stripped.startswith(("Expected:", "Received:", "Error:", "expect(")):
                message_lines.append(stripped)

        flush_message()
        return failures
