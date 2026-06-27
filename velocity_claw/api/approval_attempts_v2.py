from __future__ import annotations

from typing import Any


INSTALLATION_FLAG = "_latest_step_lookup_v2_installed"
LATEST_STEP_LOOKUP = "find_latest_step"


def find_latest_step(run: dict[str, Any], step_id: int) -> dict[str, Any] | None:
    """Return the most recent attempt for a logical step id."""
    for step in reversed(run.get("steps", [])):
        if step.get("id") == step_id:
            return step
    return None


def install_latest_step_lookup(approval_module: Any) -> None:
    if getattr(approval_module, INSTALLATION_FLAG, False):
        return

    original_approve_and_continue = approval_module.approve_and_continue

    async def approve_and_continue_with_latest_step(
        agent: Any,
        run_id: str,
        step_id: int,
        *,
        actor: str,
        reason: str | None,
    ) -> dict[str, Any]:
        run = agent.memory.load_run(run_id)
        latest = find_latest_step(run or {}, step_id)
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

    setattr(approval_module, LATEST_STEP_LOOKUP, find_latest_step)
    approval_module.approve_and_continue = approve_and_continue_with_latest_step
    setattr(approval_module, INSTALLATION_FLAG, True)
