"""Stable Dashboard v2 rendering interface."""

from typing import Any

from velocity_claw.api.dashboard_operator_renderer import (
    dashboard_risk_flags,
    html_escape,
    number_card,
    render_dashboard_v2,
    render_risk_flags,
    render_run_inspector_v2,
    run_links,
    status_badge,
)


def approval_links(run_id: Any, step_id: Any) -> str:
    """Keep the established helper links while adding direct step inspection."""
    safe_run_id = html_escape(run_id)
    safe_step_id = html_escape(step_id)
    return (
        f"<a href='/approvals/v2/{safe_run_id}/{safe_step_id}'>review</a> · "
        f"<a href='/runs/{safe_run_id}/inspect/v2?step={safe_step_id}'>inspect step</a> · "
        f"<a href='/runs/{safe_run_id}/detail/v2'>run detail</a>"
    )


__all__ = [
    "approval_links",
    "dashboard_risk_flags",
    "html_escape",
    "number_card",
    "render_dashboard_v2",
    "render_risk_flags",
    "render_run_inspector_v2",
    "run_links",
    "status_badge",
]
