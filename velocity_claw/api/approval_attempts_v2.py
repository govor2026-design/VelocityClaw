from __future__ import annotations

from typing import Any


def install_latest_step_lookup(approval_module: Any) -> None:
    if getattr(approval_module, "_latest_step_lookup_v2_installed", False):
        return

    original_approve_and_continue = approval_module.approve_and_continue

    def _find_step(run: dict[str, Any], step_id: int) -> dict[str, Any] | None:
        for step in reversed(run.get("steps", [])):
            if step.get("id") == step_id:
                return step
        return None

    async def _approve_and_continue(
        agent: Any,
        run_id: str,
        step_id: int,
        *,
        actor: str,
        reason: str | None,
    ) -> dict[str, Any]:
        run = agent.memory.load_run(run_id)
        latest = _find_step(run or {}, step_id)
        if latest and latest.get("phase") == "failed_resume":
            return await agent.approve_step(
                run_id,
                step_id,
                actor=actor,
                reason=reason,
            )
        return await original_approve_and_continue(
            agent,
            run_id,
            step_id,
            actor=actor,
            reason=reason,
        )

    approval_module._find_step = _find_step
    approval_module.approve_and_continue = _approve_and_continue
    approval_module._latest_step_lookup_v2_installed = True
