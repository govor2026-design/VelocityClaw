from __future__ import annotations

from html import escape
from typing import Any, Optional


def build_retry_controls(run: Optional[dict[str, Any]]) -> dict[str, Any]:
    if not run:
        return {
            "available": False,
            "reason": "no_run",
            "links": {},
            "html": "<p>No retry controls available.</p>",
        }

    run_id = str(run.get("run_id") or "")
    status = run.get("status")
    retryable = status in {"failed", "rejected", "awaiting_approval", "approved_waiting_manual_resume"}
    links = {
        "detail": f"/runs/{run_id}/view",
        "forensics": f"/runs/{run_id}/forensics",
        "report": f"/runs/{run_id}/report",
        "retry_context": f"/runs/{run_id}/retry-context",
        "retry_post": f"/runs/{run_id}/retry",
    }
    html = build_retry_controls_html(run, retryable=retryable, links=links)
    return {
        "available": retryable,
        "reason": "retryable" if retryable else "status_not_retryable",
        "run_id": run_id,
        "status": status,
        "task": run.get("task"),
        "links": links,
        "html": html,
    }


def build_retry_controls_html(run: dict[str, Any], *, retryable: bool, links: dict[str, str]) -> str:
    run_id = escape(str(run.get("run_id") or ""))
    task = escape(str(run.get("task") or ""))
    status = escape(str(run.get("status") or ""))
    if not retryable:
        return f"<p>Run <code>{run_id}</code> is not retryable because status is <b>{status}</b>.</p>"
    return "".join([
        "<section>",
        "<h2>Retry controls</h2>",
        f"<p>Run: <code>{run_id}</code> — {task} — <b>{status}</b></p>",
        "<ul>",
        f"<li><a href='{escape(links['detail'])}'>Open run detail</a></li>",
        f"<li><a href='{escape(links['forensics'])}'>Open forensics</a></li>",
        f"<li><a href='{escape(links['report'])}'>Open report</a></li>",
        f"<li><a href='{escape(links['retry_context'])}'>Open retry context</a></li>",
        f"<li>Retry action endpoint: <code>POST {escape(links['retry_post'])}</code></li>",
        "</ul>",
        "</section>",
    ])
