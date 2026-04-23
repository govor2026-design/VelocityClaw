from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from velocity_claw.config.settings import Settings


class ReleaseReadinessEvaluator:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.repo_root = Path(settings.workspace_root).resolve()

    def evaluate(self) -> Dict:
        checks = {
            "readme_present": self._exists("README.md"),
            "requirements_present": self._exists("requirements.txt"),
            "dockerfile_present": self._exists("Dockerfile"),
            "env_example_present": self._exists(".env.example"),
            "cli_entrypoint_present": self._exists("cli.py"),
            "api_server_present": self._exists("velocity_claw/api/server.py"),
            "telegram_bot_present": self._exists("velocity_claw/telegram_bot/bot.py"),
            "tests_present": self._has_tests(),
            "memory_enabled": bool(self.settings.memory_enabled),
            "safe_mode_configured": self.settings.safe_mode is not None,
        }
        blocking_issues: List[str] = []
        warnings: List[str] = []

        if not checks["readme_present"]:
            blocking_issues.append("README.md missing")
        if not checks["requirements_present"]:
            blocking_issues.append("requirements.txt missing")
        if not checks["env_example_present"]:
            blocking_issues.append(".env.example missing")
        if not checks["cli_entrypoint_present"]:
            blocking_issues.append("cli.py missing")
        if not checks["api_server_present"]:
            blocking_issues.append("api server missing")
        if not checks["tests_present"]:
            blocking_issues.append("tests missing")
        if not checks["dockerfile_present"]:
            warnings.append("Dockerfile missing")
        if not checks["telegram_bot_present"]:
            warnings.append("telegram bot interface missing")
        if not checks["memory_enabled"]:
            warnings.append("memory disabled in current configuration")

        score = sum(1 for value in checks.values() if value)
        total = len(checks)
        readiness = "ready" if not blocking_issues else "not_ready"
        return {
            "readiness": readiness,
            "score": score,
            "total_checks": total,
            "checks": checks,
            "blocking_issues": blocking_issues,
            "warnings": warnings,
            "packaging_targets": {
                "cli": checks["cli_entrypoint_present"],
                "api": checks["api_server_present"],
                "docker": checks["dockerfile_present"],
                "telegram": checks["telegram_bot_present"],
            },
        }

    def _exists(self, relative_path: str) -> bool:
        return (self.repo_root / relative_path).exists()

    def _has_tests(self) -> bool:
        tests_dir = self.repo_root / "tests"
        if not tests_dir.exists() or not tests_dir.is_dir():
            return False
        return any(path.suffix == ".py" for path in tests_dir.rglob("*.py"))
