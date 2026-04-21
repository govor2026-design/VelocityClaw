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


class AutoFixLoop:
    def __init__(self, patch_engine: PatchEngine, test_runner: TestRunnerTool, code_nav: CodeNavigationTool):
        self.patch_engine = patch_engine
        self.test_runner = test_runner
        self.code_nav = code_nav

    def run(self, *, target_test: str, patch_plan: List[dict], runner: str = "pytest", max_attempts: int = 2, dry_run: bool = False) -> dict:
        attempts: List[dict] = []
        previous_patch_signatures = set()
        previous_failure_signatures = set()
        for idx, patch in enumerate(patch_plan[:max_attempts], start=1):
            attempt = AutoFixAttempt(attempt=idx, reason="test failure", patches=[patch], status="running")
            attempt.target_symbols = self._extract_target_symbols(patch)
            patch_result = self.patch_engine.apply(patch, dry_run=dry_run)
            patch_signature = patch_result.get("diff", "")
            if patch_signature in previous_patch_signatures:
                attempt.status = "stopped"
                attempt.stop_reason = "repeated_patch_signature"
                attempts.append(attempt.__dict__)
                break
            previous_patch_signatures.add(patch_signature)

            test_result = self.test_runner.run(runner, target=target_test, dry_run=dry_run)
            attempt.test_result = test_result
            failure_signature = self._build_failure_signature(test_result)
            attempt.failure_signature = failure_signature
            attempt.repair_summary = self._build_repair_summary(attempt.target_symbols, test_result)

            if failure_signature and failure_signature in previous_failure_signatures:
                attempt.status = "stopped"
                attempt.stop_reason = "repeated_failure_signature"
                attempts.append(attempt.__dict__)
                break
            if failure_signature:
                previous_failure_signatures.add(failure_signature)

            attempt.status = "passed" if test_result["status"] in {"passed", "simulated"} else "failed"
            attempts.append(attempt.__dict__)
            if test_result["status"] in {"passed", "simulated"}:
                return {
                    "mode": "auto_fix",
                    "max_attempts": max_attempts,
                    "attempts": attempts,
                    "status": "completed",
                }
        return {
            "mode": "auto_fix",
            "max_attempts": max_attempts,
            "attempts": attempts,
            "status": "failed",
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
