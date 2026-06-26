from __future__ import annotations

from typing import Any

from velocity_claw.memory.step_attempts_v2 import effective_steps


def _simulation_items(run: dict[str, Any]) -> list[dict[str, Any]]:
    items = []
    for step in effective_steps(run.get("steps") or []):
        result = step.get("result")
        simulated = bool(step.get("simulated")) or (
            isinstance(result, dict) and result.get("status") == "simulated"
        )
        if not simulated:
            continue
        items.append(
            {
                "id": step.get("id"),
                "title": step.get("title"),
                "tool": step.get("tool"),
                "action": result.get("action") if isinstance(result, dict) else step.get("tool"),
                "path": result.get("path") if isinstance(result, dict) else None,
                "command": result.get("command") if isinstance(result, dict) else None,
                "validated": result.get("validated") if isinstance(result, dict) else None,
                "attempt_no": step.get("attempt_no", 1),
                "phase": step.get("phase", "initial"),
            }
        )
    return items


def install_dry_run_reporting(memory_cls: type) -> None:
    if getattr(memory_cls, "_dry_run_reporting_installed", False):
        return

    original_forensics = memory_cls.build_run_forensics
    original_report = memory_cls.build_run_report

    def build_run_forensics(self, run: dict[str, Any]) -> dict[str, Any]:
        payload = original_forensics(self, run)
        simulations = _simulation_items(run)
        payload["dry_run"] = {
            "simulated_count": len(simulations),
            "simulated_steps": simulations,
        }
        return payload

    def build_run_report(self, run: dict[str, Any]) -> dict[str, Any]:
        payload = original_report(self, run)
        simulations = _simulation_items(run)
        payload["dry_run_overview"] = {
            "enabled_for_run": bool(simulations),
            "simulated_count": len(simulations),
            "simulated_steps": simulations,
        }
        if simulations and payload.get("executive_summary"):
            payload["executive_summary"] += (
                f" Dry-run simulated {len(simulations)} action(s); no listed mutation was applied."
            )
        return payload

    memory_cls.build_run_forensics = build_run_forensics
    memory_cls.build_run_report = build_run_report
    memory_cls._dry_run_reporting_installed = True
