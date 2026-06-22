from __future__ import annotations

import json
from html import escape
from typing import Any
from urllib.parse import urlencode

from velocity_claw.__version__ import __release_stage__, __version__


def html_escape(value: Any) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def status_badge(status: str) -> str:
    normalized = (status or "unknown").lower().replace("_", "-")
    return f"<span class='badge badge-{html_escape(normalized)}'>{html_escape(status or 'unknown')}</span>"


def number_card(label: str, value: Any) -> str:
    return (
        "<section class='card metric'>"
        f"<div class='label'>{html_escape(label)}</div>"
        f"<div class='value'>{html_escape(value)}</div>"
        "</section>"
    )


def run_links(run_id: Any) -> str:
    safe_run_id = html_escape(run_id)
    return (
        f"<a href='/runs/{safe_run_id}/inspect/v2'>inspect</a> · "
        f"<a href='/runs/{safe_run_id}/detail/v2'>detail json</a> · "
        f"<a href='/runs/{safe_run_id}/artifacts/v2'>artifacts json</a> · "
        f"<a href='/runs/{safe_run_id}/forensics'>forensics</a> · "
        f"<a href='/runs/{safe_run_id}/report'>report</a> · "
        f"<a href='/runs/{safe_run_id}/view'>classic</a>"
    )


def approval_links(run_id: Any, step_id: Any) -> str:
    safe_run_id = html_escape(run_id)
    safe_step_id = html_escape(step_id)
    return (
        f"<a href='/approvals/v2/{safe_run_id}/{safe_step_id}'>review</a> · "
        f"<a href='/runs/{safe_run_id}/inspect/v2?step={safe_step_id}'>inspect step</a>"
    )


def dashboard_risk_flags(
    *,
    trusted_mode: bool,
    release_state: dict[str, Any],
    queue_summary: dict[str, Any],
    approvals: list[dict[str, Any]],
    provider_summary: dict[str, Any],
    last_failed: dict[str, Any] | None,
) -> list[dict[str, str]]:
    flags: list[dict[str, str]] = []
    if trusted_mode:
        flags.append({"level": "high", "code": "trusted_mode", "message": "Trusted mode is enabled."})
    if release_state.get("readiness") not in {"ready", "ok"}:
        flags.append({"level": "medium", "code": "release_readiness", "message": "Release readiness is not green."})
    if queue_summary.get("failed", 0) > 0:
        flags.append({"level": "medium", "code": "queue_failed", "message": "Queue has failed jobs."})
    if approvals:
        flags.append({"level": "info", "code": "pending_approvals", "message": "Pending approvals require review."})
    if provider_summary.get("failed_routes", 0) > 0:
        flags.append({"level": "medium", "code": "provider_routes", "message": "Provider routing has failed routes."})
    if last_failed:
        flags.append({"level": "info", "code": "last_failed_run", "message": "A failed run is available for inspection."})
    return flags


def render_risk_flags(flags: list[dict[str, str]]) -> str:
    if not flags:
        return "<p>No active risk flags. <a href='/diagnostics/v2'>Open Diagnostics v2</a></p>"
    items = "".join(
        "<li>"
        f"{status_badge(flag.get('level', 'info'))} "
        f"<code>{html_escape(flag.get('code'))}</code> — {html_escape(flag.get('message'))}"
        "</li>"
        for flag in flags
    )
    return f"<ul>{items}</ul><p><a href='/diagnostics/v2'>Open Diagnostics v2</a></p>"


def _option(value: str, selected: str | None, label: str | None = None) -> str:
    selected_attr = " selected" if value == (selected or "") else ""
    return f"<option value='{html_escape(value)}'{selected_attr}>{html_escape(label or value)}</option>"


def _filter_form(
    filters: dict[str, str],
    available_statuses: list[str],
    available_profiles: list[str],
) -> str:
    status = filters.get("status", "")
    profile = filters.get("profile", "")
    query = filters.get("q", "")
    status_options = _option("", status, "all statuses") + "".join(
        _option(item, status) for item in available_statuses
    )
    profile_options = _option("", profile, "all profiles") + "".join(
        _option(item, profile) for item in available_profiles
    )
    return f"""
    <form class='filters' method='get' action='/dashboard/v2'>
      <label>Status<select name='status'>{status_options}</select></label>
      <label>Profile<select name='profile'>{profile_options}</select></label>
      <label class='grow'>Task or run ID<input name='q' value='{html_escape(query)}' placeholder='queue, approval, run id'></label>
      <button type='submit'>Apply</button>
      <a class='button secondary' href='/dashboard/v2'>Clear</a>
    </form>
    """


def render_dashboard_v2(
    *,
    execution_profile: str,
    safe_mode: bool,
    trusted_mode: bool,
    release_state: dict[str, Any],
    console: dict[str, Any],
    recent_runs: list[dict[str, Any]],
    approvals: list[dict[str, Any]],
    queue_jobs: list[dict[str, Any]],
    metrics: dict[str, Any],
    provider_observability: dict[str, Any],
    provider_health: dict[str, Any],
    last_failed: dict[str, Any] | None,
    filters: dict[str, str] | None = None,
    available_statuses: list[str] | None = None,
    available_profiles: list[str] | None = None,
    total_run_count: int | None = None,
) -> str:
    filters = filters or {}
    available_statuses = available_statuses or sorted({str(item.get("status") or "unknown") for item in recent_runs})
    available_profiles = available_profiles or sorted({str(item.get("execution_profile") or "unknown") for item in recent_runs})
    release_score = f"{release_state.get('score', 0)}/{release_state.get('total_checks', 0)}"
    provider_summary = provider_observability.get("summary", {}) if isinstance(provider_observability, dict) else {}
    queue_summary = console.get("queue", {}) if isinstance(console, dict) else {}
    approval_summary = console.get("approvals", {}) if isinstance(console, dict) else {}
    risk_flags = dashboard_risk_flags(
        trusted_mode=trusted_mode,
        release_state=release_state,
        queue_summary=queue_summary,
        approvals=approvals,
        provider_summary=provider_summary,
        last_failed=last_failed,
    )

    run_rows = []
    for run in recent_runs:
        run_id = run.get("run_id", "")
        run_rows.append(
            "<tr>"
            f"<td><code>{html_escape(run_id)}</code></td>"
            f"<td>{html_escape(run.get('task'))}</td>"
            f"<td>{status_badge(str(run.get('status') or 'unknown'))}</td>"
            f"<td>{html_escape(run.get('execution_profile') or 'unknown')}</td>"
            f"<td>{html_escape(run.get('created_at'))}</td>"
            f"<td>{run_links(run_id)}</td>"
            "</tr>"
        )

    approval_rows = []
    for item in approvals:
        run_id = item.get("run_id")
        step_id = item.get("step_id")
        approval_rows.append(
            "<tr>"
            f"<td><code>{html_escape(run_id)}</code></td>"
            f"<td>{html_escape(step_id)}</td>"
            f"<td>{html_escape(item.get('title') or item.get('step_title') or '')}</td>"
            f"<td>{html_escape(item.get('reason') or item.get('approval_reason') or '')}</td>"
            f"<td>{approval_links(run_id, step_id)}</td>"
            "</tr>"
        )

    queue_rows = []
    for job in queue_jobs:
        queue_rows.append(
            "<tr>"
            f"<td><code>{html_escape(job.get('job_id'))}</code></td>"
            f"<td>{html_escape(job.get('task'))}</td>"
            f"<td>{status_badge(str(job.get('status') or 'unknown'))}</td>"
            f"<td>{html_escape(job.get('attempts'))}</td>"
            f"<td>{html_escape(job.get('terminal_reason') or '')}</td>"
            "</tr>"
        )

    provider_rows = []
    for provider, state in provider_health.items():
        provider_rows.append(
            "<tr>"
            f"<td>{html_escape(provider)}</td>"
            f"<td>{html_escape(state.get('requests', 0))}</td>"
            f"<td>{html_escape(state.get('successes', 0))}</td>"
            f"<td>{html_escape(state.get('failures', 0))}</td>"
            f"<td>{status_badge('cooldown' if state.get('in_cooldown') else 'ready')}</td>"
            f"<td>{html_escape(state.get('last_error') or '')}</td>"
            "</tr>"
        )

    last_failed_block = "<p>No failed runs recorded.</p>"
    if last_failed:
        run_id = last_failed.get("run_id", "")
        last_failed_block = (
            f"<p><code>{html_escape(run_id)}</code> — {html_escape(last_failed.get('task'))} "
            f"{status_badge(str(last_failed.get('status') or 'failed'))} "
            f"{run_links(run_id)}</p>"
        )

    shown = len(recent_runs)
    total = total_run_count if total_run_count is not None else shown
    filter_summary = f"Showing {shown} of {total} recent runs."
    if any(filters.values()):
        filter_summary += " Filters are active."

    return f"""
<!doctype html>
<html lang='en'>
<head>
  <meta charset='utf-8'>
  <meta name='viewport' content='width=device-width, initial-scale=1'>
  <title>Velocity Claw Dashboard v2</title>
  <style>
    :root {{ color-scheme: dark; --bg:#0f172a; --panel:#111827; --muted:#94a3b8; --text:#e5e7eb; --line:#263244; --accent:#38bdf8; }}
    body {{ margin:0; font-family:ui-sans-serif,system-ui,-apple-system,Segoe UI,Arial,sans-serif; background:var(--bg); color:var(--text); }}
    main {{ max-width:1380px; margin:0 auto; padding:28px; }}
    header {{ display:flex; justify-content:space-between; gap:18px; align-items:flex-start; margin-bottom:24px; }}
    h1 {{ margin:0; font-size:32px; }} h2 {{ margin:0 0 12px; font-size:20px; }}
    a {{ color:var(--accent); text-decoration:none; }} .muted {{ color:var(--muted); }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(210px,1fr)); gap:14px; margin:18px 0; }}
    .card {{ background:var(--panel); border:1px solid var(--line); border-radius:16px; padding:16px; box-shadow:0 8px 24px rgba(0,0,0,.18); }}
    .metric .label {{ color:var(--muted); font-size:13px; }} .metric .value {{ font-size:26px; font-weight:700; margin-top:6px; }}
    .section {{ margin-top:18px; overflow:auto; }} table {{ width:100%; border-collapse:collapse; min-width:780px; }}
    th,td {{ border-bottom:1px solid var(--line); padding:10px; text-align:left; vertical-align:top; }} th {{ color:var(--muted); font-size:13px; }}
    code,pre {{ background:#020617; border:1px solid var(--line); border-radius:8px; }} code {{ padding:2px 6px; }} pre {{ padding:12px; overflow:auto; }}
    .badge {{ display:inline-block; border:1px solid var(--line); border-radius:999px; padding:2px 8px; font-size:12px; }}
    .badge-completed,.badge-ok,.badge-ready {{ border-color:#22c55e; color:#86efac; }}
    .badge-failed,.badge-error,.badge-high,.badge-rejected {{ border-color:#ef4444; color:#fca5a5; }}
    .badge-running,.badge-pending,.badge-pending-approval,.badge-cooldown,.badge-medium {{ border-color:#f59e0b; color:#fcd34d; }}
    .badge-info,.badge-awaiting-approval {{ border-color:#38bdf8; color:#7dd3fc; }}
    .nav {{ display:flex; flex-wrap:wrap; gap:10px; margin-top:10px; }} .nav a,.button {{ background:#020617; border:1px solid var(--line); border-radius:999px; padding:8px 10px; }}
    .filters {{ display:flex; flex-wrap:wrap; gap:12px; align-items:end; }} .filters label {{ display:flex; flex-direction:column; gap:5px; color:var(--muted); font-size:13px; }}
    .filters .grow {{ flex:1 1 280px; }} input,select,button {{ min-height:40px; box-sizing:border-box; border:1px solid var(--line); border-radius:9px; padding:8px 10px; background:#020617; color:var(--text); }}
    button {{ cursor:pointer; color:var(--accent); }} .secondary {{ color:var(--muted); }} ul {{ margin:0; padding-left:20px; }} li {{ margin:7px 0; }}
  </style>
</head>
<body><main>
  <header><div>
    <h1>Velocity Claw Dashboard v2</h1>
    <p class='muted'>Operational overview with server-side run filters and direct inspection.</p>
    <div class='nav'>
      <a href='/version'>version</a><a href='/dashboard'>classic dashboard</a><a href='/diagnostics/v2'>diagnostics v2</a>
      <a href='/ops/console'>ops console</a><a href='/runs'>runs json</a><a href='/approvals/v2'>approvals v2</a>
      <a href='/queue/v2/runtime'>queue v2</a><a href='/metrics'>metrics json</a>
    </div>
  </div><section class='card'>
    <div>Version: <b>{html_escape(__version__)}</b> <span class='muted'>({html_escape(__release_stage__)})</span></div>
    <div>Profile: <b>{html_escape(execution_profile)}</b></div><div>Safe mode: <b>{html_escape(safe_mode)}</b></div>
    <div>Trusted mode: <b>{html_escape(trusted_mode)}</b></div>
  </section></header>

  <section class='card'>{_filter_form(filters, available_statuses, available_profiles)}<p class='muted'>{html_escape(filter_summary)}</p></section>

  <div class='grid'>
    {number_card('Version', __version__)}{number_card('Release readiness', release_state.get('readiness', 'unknown'))}
    {number_card('Release score', release_score)}{number_card('Runs shown', shown)}
    {number_card('Queue running', queue_summary.get('running', 0))}{number_card('Queue failed', queue_summary.get('failed', 0))}
    {number_card('Approvals pending', approval_summary.get('pending', len(approvals)))}{number_card('Risk flags', len(risk_flags))}
  </div>

  <section class='card section'><h2>Diagnostics</h2>{render_risk_flags(risk_flags)}</section>
  <section class='card section'><h2>Last failed run</h2>{last_failed_block}</section>
  <section class='card section'><h2>Recent runs</h2>
    <table><thead><tr><th>Run ID</th><th>Task</th><th>Status</th><th>Profile</th><th>Created</th><th>Links</th></tr></thead><tbody>
      {''.join(run_rows) or "<tr><td colspan='6'>No runs match the selected filters.</td></tr>"}
    </tbody></table>
  </section>
  <section class='card section'><h2>Pending approvals</h2>
    <table><thead><tr><th>Run ID</th><th>Step</th><th>Title</th><th>Reason</th><th>Links</th></tr></thead><tbody>
      {''.join(approval_rows) or "<tr><td colspan='5'>No pending approvals.</td></tr>"}
    </tbody></table>
  </section>
  <section class='card section'><h2>Queue</h2>
    <table><thead><tr><th>Job ID</th><th>Task</th><th>Status</th><th>Attempts</th><th>Terminal reason</th></tr></thead><tbody>
      {''.join(queue_rows) or "<tr><td colspan='5'>No queued jobs.</td></tr>"}
    </tbody></table>
  </section>
  <section class='card section'><h2>Provider health</h2>
    <table><thead><tr><th>Provider</th><th>Requests</th><th>Successes</th><th>Failures</th><th>State</th><th>Last error</th></tr></thead><tbody>
      {''.join(provider_rows) or "<tr><td colspan='6'>No provider health data.</td></tr>"}
    </tbody></table>
  </section>
  <section class='card section'><h2>Raw metric counters</h2><pre>{html_escape(json.dumps(metrics, ensure_ascii=False, indent=2, default=str))}</pre></section>
</main></body></html>
""".strip()


def _inspector_url(run_id: str, *, step: Any = None, artifact_type: str | None = None) -> str:
    params = {}
    if step is not None:
        params["step"] = step
    if artifact_type:
        params["artifact_type"] = artifact_type
    query = urlencode(params)
    return f"/runs/{html_escape(run_id)}/inspect/v2" + (f"?{query}" if query else "")


def render_run_inspector_v2(
    run: dict[str, Any],
    *,
    selected_step_id: int | None = None,
    artifact_type: str | None = None,
) -> str:
    run_id = str(run.get("run_id") or "")
    steps = run.get("steps") or []
    artifacts = run.get("artifacts") or []
    available_types = sorted({str(item.get("artifact_type") or "text") for item in artifacts})
    selected_step = next((item for item in steps if item.get("id") == selected_step_id), None)
    visible_artifacts = [
        item for item in artifacts
        if not artifact_type or str(item.get("artifact_type") or "text") == artifact_type
    ]
    if selected_step_id is not None:
        visible_artifacts = [item for item in visible_artifacts if item.get("step_id") == selected_step_id]

    step_rows = []
    for step in steps:
        step_id = step.get("id")
        step_rows.append(
            "<tr>"
            f"<td>{html_escape(step_id)}</td><td>{html_escape(step.get('title'))}</td>"
            f"<td><code>{html_escape(step.get('tool') or '')}</code></td>"
            f"<td>{status_badge(str(step.get('status') or 'unknown'))}</td>"
            f"<td>{html_escape(step.get('error') or '')}</td>"
            f"<td><a href='{_inspector_url(run_id, step=step_id, artifact_type=artifact_type)}'>inspect</a></td>"
            "</tr>"
        )

    selected_block = "<p class='muted'>Select a step to inspect arguments, result, errors, and matching artifacts.</p>"
    if selected_step_id is not None and selected_step is None:
        selected_block = f"<p class='error'>Step {html_escape(selected_step_id)} was not found.</p>"
    elif selected_step is not None:
        selected_block = (
            f"<h3>Step {html_escape(selected_step.get('id'))}: {html_escape(selected_step.get('title'))}</h3>"
            f"<p>Tool: <code>{html_escape(selected_step.get('tool') or '')}</code> · Status: {status_badge(str(selected_step.get('status') or 'unknown'))}</p>"
            f"<h4>Arguments</h4><pre>{html_escape(json.dumps(selected_step.get('args') or {}, ensure_ascii=False, indent=2, default=str))}</pre>"
            f"<h4>Result</h4><pre>{html_escape(json.dumps(selected_step.get('result'), ensure_ascii=False, indent=2, default=str))}</pre>"
            f"<h4>Error</h4><pre>{html_escape(selected_step.get('error') or '')}</pre>"
        )

    type_options = _option("", artifact_type, "all artifact types") + "".join(
        _option(item, artifact_type) for item in available_types
    )
    artifact_blocks = []
    for artifact in visible_artifacts:
        content = artifact.get("content") or ""
        artifact_blocks.append(
            "<details class='artifact'>"
            f"<summary><b>{html_escape(artifact.get('name'))}</b> "
            f"{status_badge(str(artifact.get('artifact_type') or 'text'))} "
            f"step {html_escape(artifact.get('step_id') if artifact.get('step_id') is not None else 'run')}</summary>"
            f"<div class='muted'>Created: {html_escape(artifact.get('created_at') or '')}</div>"
            f"<pre>{html_escape(content)}</pre></details>"
        )

    report = run.get("report") or {}
    forensics = run.get("forensics") or {}
    return f"""
<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Run inspector {html_escape(run_id)}</title><style>
:root {{ color-scheme:dark; --bg:#0f172a; --panel:#111827; --muted:#94a3b8; --text:#e5e7eb; --line:#263244; --accent:#38bdf8; }}
body {{ margin:0; font-family:ui-sans-serif,system-ui,sans-serif; background:var(--bg); color:var(--text); }} main {{ max-width:1380px; margin:auto; padding:28px; }}
a {{ color:var(--accent); text-decoration:none; }} .card {{ background:var(--panel); border:1px solid var(--line); border-radius:16px; padding:16px; margin-top:16px; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(240px,1fr)); gap:12px; }} .muted {{ color:var(--muted); }} .error {{ color:#fca5a5; }}
table {{ width:100%; border-collapse:collapse; min-width:760px; }} th,td {{ padding:10px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; }} .scroll {{ overflow:auto; }}
code,pre {{ background:#020617; border:1px solid var(--line); border-radius:8px; }} code {{ padding:2px 6px; }} pre {{ padding:12px; overflow:auto; white-space:pre-wrap; word-break:break-word; }}
.badge {{ display:inline-block; border:1px solid var(--line); border-radius:999px; padding:2px 8px; font-size:12px; }} .badge-completed,.badge-success,.badge-approved,.badge-ready {{ color:#86efac; border-color:#22c55e; }}
.badge-failed,.badge-rejected,.badge-error {{ color:#fca5a5; border-color:#ef4444; }} .badge-running,.badge-pending-approval {{ color:#fcd34d; border-color:#f59e0b; }}
.filters {{ display:flex; flex-wrap:wrap; gap:10px; align-items:end; }} label {{ display:flex; flex-direction:column; gap:5px; color:var(--muted); }} select,button {{ min-height:40px; background:#020617; color:var(--text); border:1px solid var(--line); border-radius:8px; padding:8px; }}
.artifact {{ border:1px solid var(--line); border-radius:10px; padding:10px; margin:10px 0; }} summary {{ cursor:pointer; }}
</style></head><body><main>
<p><a href='/dashboard/v2'>← Dashboard v2</a> · <a href='/runs/{html_escape(run_id)}/detail/v2'>detail JSON</a> · <a href='/runs/{html_escape(run_id)}/artifacts/v2'>artifacts JSON</a></p>
<h1>Run inspector</h1><p><code>{html_escape(run_id)}</code></p>
<div class='grid'>
<section class='card'><b>Task</b><p>{html_escape(run.get('task'))}</p></section>
<section class='card'><b>Status</b><p>{status_badge(str(run.get('status') or 'unknown'))}</p></section>
<section class='card'><b>Profile</b><p>{html_escape(run.get('execution_profile') or 'unknown')}</p></section>
<section class='card'><b>Created</b><p>{html_escape(run.get('created_at') or '')}</p></section>
</div>
<section class='card'><h2>Summary</h2><p>{html_escape(report.get('executive_summary') or 'No report summary available.')}</p>
<p>Steps: <b>{html_escape(forensics.get('step_count', len(steps)))}</b> · Artifacts: <b>{html_escape(forensics.get('artifact_count', len(artifacts)))}</b></p></section>
<section class='card scroll'><h2>Steps</h2><table><thead><tr><th>ID</th><th>Title</th><th>Tool</th><th>Status</th><th>Error</th><th>Action</th></tr></thead><tbody>
{''.join(step_rows) or "<tr><td colspan='6'>No steps recorded.</td></tr>"}</tbody></table></section>
<section class='card'><h2>Step inspector</h2>{selected_block}</section>
<section class='card'><h2>Artifacts</h2>
<form class='filters' method='get' action='/runs/{html_escape(run_id)}/inspect/v2'>
{f"<input type='hidden' name='step' value='{html_escape(selected_step_id)}'>" if selected_step_id is not None else ''}
<label>Artifact type<select name='artifact_type'>{type_options}</select></label><button type='submit'>Apply</button>
<a href='{_inspector_url(run_id, step=selected_step_id)}'>Clear type</a><a href='{_inspector_url(run_id)}'>Show all steps</a>
</form>
{''.join(artifact_blocks) or "<p class='muted'>No artifacts match the selected step and type.</p>"}
</section></main></body></html>
""".strip()
