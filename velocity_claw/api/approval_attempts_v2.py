from __future__ import annotations

from typing import Any


def install_latest_step_lookup(approval_module: Any) -> None:
    if getattr(approval_module, "_latest_step_lookup_v2_installed", False):
        return

    def _find_step(run: dict[str, Any], step_id: int) -> dict[str, Any] | None:
        for step in reversed(run.get("steps", [])):
            if step.get("id") == step_id:
                return step
        return None

    approval_module._find_step = _find_step
    approval_module._latest_step_lookup_v2_installed = True
