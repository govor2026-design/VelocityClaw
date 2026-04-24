from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from velocity_claw.tools.patch import PatchEngine
from velocity_claw.tools.test_runner import TestRunnerTool
from velocity_claw.tools.code_nav import CodeNavigationTool


@dataclass
class AutoFixAttempt:
    attempt: int
    reason: str
    target_symbols: List[str] = field(default_factory=list)
    patches: List[dict] = field(default_factory=list)
    test_result: Optional[dict] = None
    status: str = "pending"
    stop_reason: Optional[str] = None
    failure_signature: Optional[str] = None
    repair_summary: Optional[dict] = None
    forensic_summary: Optional[dict] = None


class AutoFixLoop:
    def __init__(self, patch_engine: PatchEngine, test_runner: TestRunnerTool, code_nav: CodeNavigationTool):
        self.patch_engine = patch_engine
        self.test_runner = test_runner
        self.code_nav = code_nav

    def run(self, *, target_test: str, patch_plan: List[dict], runner: str = "pytest", max_attempts: int = 2, dry_run: bool = False) -> dict:
        attempts: List[dict] = []
        previous_patch_signatures = set()
        previous_failure_signatures = set()
        final_stop_reason: Optional[str] = None

        for idx, patch in enumerate(patch_plan[:max_attempts], start=1):
            attempt = AutoFixAttempt(attempt=idx, reason="test failure", patches=[patch], status="running")
            attempt.target_symbols = self._extract_target_symbols(patch)
            patch_result = self.patch_engine.apply(patch, dry_run=dry_run)
            patch_signature = patch_result.get("diff", "")

            if patch_signature in previous_patch_signatures:
                attempt.status = "stopped"
                attempt.stop_reason = "repeated_patch_signature"
                attempt.forensic_summary = self._build_forensic_summary(attempt, patch_result, None)
                attempts.append(attempt.__dict__)
                final_stop_reason = attempt.stop_reason
                break
            previous_patch_signatures.add(patch_signature)

            test_result = self.test_runner.run(runner, target=target_test, dry_run=dry_run)
            attempt.test_result = test_result
            failure_signature = self._build_failure_signature(test_result)
            attempt.failure_signature = failure_signature
            attempt.repair_summary = self._build_repair_summary(attempt.target_symbols, test_result)
            attempt.forensic_summary = self._build_forensic_summary(attempt, patch_result, test_result)

            if failure_signature and failure_signature in previous_failure_signatures:
                attempt.status = "stopped"
                attempt.stop_reason = "repeated_failure_signature"
                attempts.append(attempt.__dict__)
                final_stop_reason = attempt.stop_reason
                break
            if failure_signature:
                previous_failure_signatures.add(failure_signature)

            attempt.status = "passed" if test_result["status"] == "passed" else ("simulated" if test_result["status"] == "simulated" else "failed")
            attempts.append(attempt.__dict__)
            if test_result["status"] == "passed":
                return {
                    "mode": "auto_fix",
                    "max_attempts": max_attempts,
                    "attempts": attempts,
                    "status": "completed",
                    "stop_reason": "tests_passed",
                    "forensics": self._build_loop_forensics(attempts, "tests_passed"),
                }

        if not final_stop_reason:
            final_stop_reason = "max_attempts_reached" if attempts else "no_attempts_executed"
        return {
            "mode": "auto_fix",
            "max_attempts": max_attempts,
            "attempts": attempts,
            "status": "failed",
            "stop_reason": final_stop_reason,
            "forensics": self._build_loop_forensics(attempts, final_stop_reason),
        }

    def _extract_target_symbols(self, patch: dict) -> List[str]:
        symbols = []
        if patch.get("name"):
            symbols.append(patch["name"])
        for key in ("target", "replacement"):
            value = patch.get(key)
            if isinstance(value, str) and value.isidentifier():
                symbols.append(value)
        return symbols

    def _build_failure_signature(self, test_result: dict) -> Optional[str]:
        failures = test_result.get("parsed_failures") or []
        if not failures:
            return None
        parts = []
        for failure in failures:
            parts.append(
                "|".join(
                    [
                        failure.get("nodeid") or failure.get("failed_test_name") or "?",
                        str(failure.get("file") or "?"),
                        str(failure.get("line") or "?"),
                        str(failure.get("assertion") or "?"),
                    ]
                )
            )
        return "::".join(parts)

    def _build_repair_summary(self, target_symbols: List[str], test_result: dict) -> dict:
        summary = {
            "target_symbols": target_symbols,
            "symbol_matches": {},
            "failed_tests": [],
        }
        for symbol in target_symbols:
            summary["symbol_matches"][symbol] = self.code_nav.explain_ambiguity(symbol)
        for failure in test_result.get("parsed_failures") or []:
            summary["failed_tests"].append(
                {
                    "nodeid": failure.get("nodeid") or failure.get("failed_test_name"),
                    "file": failure.get("file"),
                    "line": failure.get("line"),
                    "assertion": failure.get("assertion"),
                }
            )
        return summary

    def _build_forensic_summary(self, attempt: AutoFixAttempt, patch_result: Optional[dict], test_result: Optional[dict]) -> dict:
        diff_preview = (patch_result or {}).get("diff", "")[:300]
        failures = (test_result or {}).get("parsed_failures") or []
        stdout_preview = (test_result or {}).get("stdout", "")[:300]
        return {
            "attempt": attempt.attempt,
            "target_symbols": attempt.target_symbols,
            "patch_diff_preview": diff_preview,
            "test_status": (test_result or {}).get("status"),
            "failure_count": len(failures),
            "failed_tests": [
                {
                    "nodeid": failure.get("nodeid") or failure.get("failed_test_name"),
                    "file": failure.get("file"),
                    "line": failure.get("line"),
                }
                for failure in failures[:5]
            ],
            "stdout_preview": stdout_preview,
        }

    def _build_loop_forensics(self, attempts: List[dict], stop_reason: str) -> dict:
        last_attempt = attempts[-1] if attempts else None
        return {
            "attempt_count": len(attempts),
            "stop_reason": stop_reason,
            "last_attempt_status": last_attempt.get("status") if last_attempt else None,
            "last_failure_signature": last_attempt.get("failure_signature") if last_attempt else None,
            "attempt_statuses": [item.get("status") for item in attempts],
        }
