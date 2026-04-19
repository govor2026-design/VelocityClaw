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


class AutoFixLoop:
    def __init__(self, patch_engine: PatchEngine, test_runner: TestRunnerTool, code_nav: CodeNavigationTool):
        self.patch_engine = patch_engine
        self.test_runner = test_runner
        self.code_nav = code_nav

    def run(self, *, target_test: str, patch_plan: List[dict], runner: str = "pytest", max_attempts: int = 2, dry_run: bool = False) -> dict:
        attempts: List[dict] = []
        previous_signatures = set()
        for idx, patch in enumerate(patch_plan[:max_attempts], start=1):
            attempt = AutoFixAttempt(attempt=idx, reason="test failure", patches=[patch], status="running")
            patch_result = self.patch_engine.apply(patch, dry_run=dry_run)
            signature = patch_result.get("diff", "")
            if signature in previous_signatures:
                attempt.status = "stopped_repeated_failure"
                attempts.append(attempt.__dict__)
                break
            previous_signatures.add(signature)
            test_result = self.test_runner.run(runner, target=target_test, dry_run=dry_run)
            attempt.test_result = test_result
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
