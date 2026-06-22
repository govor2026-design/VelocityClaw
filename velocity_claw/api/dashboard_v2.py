from __future__ import annotations

import re
from html import escape
from typing import Any

from velocity_claw.__version__ import __release_stage__, __version__


def html_escape(value: Any) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def _css_token(value: Any) -> str:
    token = re.sub(r"[^a-z0-9_-]+", "-", str(value or "unknown").strip().lower())
    return token.strip("-") or "unknown"


def status_badge(status: str) -> str:
    normalized = _css_token(status)
    return f"<span class='badge badge-{normalized}'>{html_escape(status or 'unknown')}</span>"


def number_card(label: str, value: Any) -> str:
    return f"<section class='card metric'><div class='label'>{html_escape(label)}</div><div class='value'>{html_escape(value)}</div></section>"


def run_links(run_id: Any) -> str:
    safe_run_id = html_escape(run_id)
    return (
        f"<a href='/runs/{safe_run_id}/view'>inspect</a> · "
        f"<a href='/runs/{safe_run_id}/detail/v2'>detail json</a> · "
        f"<a href='/runs/{safe_run_id}/artifacts/v2'>artifacts json</a> · "
        f"<a href='/runs/{safe_run_id}/forensics'>forensics</a> · "
        f"<a href='/runs/{safe_run_id}/report'>report</a>"
    )


def approval_links(run_id: Any, step_id: Any) -> str:
    safe_run_id = html_escape(run_id)
    safe_step_id = html_escape(step_id)
    return (
        f"<a href='/approvals/v2/{safe_run_id}/{safe_step_id}'>review</a> · "
        f"<a href='/runs/{safe_run_id}/view'>inspect run</a>"
    )


def _filter_options(values: list[str], label: str) -> str:
    options = [f"<option value=''>All {html_escape(label)}</option>"]
    for value in sorted({item for item in values if item}):
        options.append(f"<option value='{html_escape(value)}'>{html_escape(value)}</option>")
    return "".join(options)


def dashboard_risk_flags(*, trusted_mode: bool, release_state: dict[str, Any], queue_summary: dict[str, Any], approvals: list[dict[str, Any]], provider_summary: dict[str, Any], last_failed: dict[str, Any] | None) -> list[dict[str, str]]:
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
) -> str:
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
    run_statuses: list[str] = []
    run_profiles: list[str] = []
    for run in recent_runs:
        run_id = run.get("run_id", "")
        status = str(run.get("status") or "unknown").lower()
        profile = str(run.get("execution_profile") or "unknown").lower()
        run_statuses.append(status)
        run_profiles.append(profile)
        run_rows.append(
            f"<tr class='run-row' data-status='{html_escape(status)}' data-profile='{html_escape(profile)}'>"
            f"<td><a href='/runs/{html_escape(run_id)}/view'><code>{html_escape(run_id)}</code></a></td>"
            f"<td>{html_escape(run.get('task'))}</td>"
            f"<td>{status_badge(status)}</td>"
            f"<td><code>{html_escape(profile)}</code></td>"
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
    for provider, state in (provider_health or {}).items():
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

    last_failed_block = "<p class='empty-state'>No failed runs recorded.</p>"
    if last_failed:
        run_id = last_failed.get("run_id", "")
        last_failed_block = (
            f"<p><code>{html_escape(run_id)}</code> — {html_escape(last_failed.get('task'))} "
            f"{status_badge(str(last_failed.get('status') or 'failed'))} "
            f"{run_links(run_id)}</p>"
        )

    status_options = _filter_options(run_statuses, "statuses")
    profile_options = _filter_options(run_profiles, "profiles")
    recorded_empty = "" if run_rows else "<tr id='runs-recorded-empty'><td colspan='6' class='empty-state'>No runs recorded yet.</td></tr>"

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
    main {{ max-width:1280px; margin:0 auto; padding:28px; }}
    header {{ display:flex; justify-content:space-between; gap:18px; align-items:flex-start; margin-bottom:24px; }}
    h1 {{ margin:0; font-size:32px; }}
    h2 {{ margin:0 0 12px; font-size:20px; }}
    a {{ color:var(--accent); text-decoration:none; }}
    .muted,.empty-state {{ color:var(--muted); }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:14px; margin:18px 0; }}
    .card {{ background:var(--panel); border:1px solid var(--line); border-radius:16px; padding:16px; box-shadow:0 8px 24px rgba(0,0,0,.18); }}
    .metric .label {{ color:var(--muted); font-size:13px; }}
    .metric .value {{ font-size:26px; font-weight:700; margin-top:6px; }}
    .section {{ margin-top:18px; }}
    table {{ width:100%; border-collapse:collapse; overflow:hidden; border-radius:12px; }}
    th,td {{ border-bottom:1px solid var(--line); padding:10px; text-align:left; vertical-align:top; }}
    th {{ color:var(--muted); font-size:13px; font-weight:600; }}
    code,pre {{ background:#020617; border:1px solid var(--line); border-radius:8px; }}
    code {{ padding:2px 6px; }}
    pre {{ padding:12px; overflow:auto; }}
    .badge {{ display:inline-block; border:1px solid var(--line); border-radius:999px; padding:2px 8px; font-size:12px; }}
    .badge-completed,.badge-success,.badge-passed,.badge-ok,.badge-ready {{ border-color:#22c55e; color:#86efac; }}
    .badge-failed,.badge-error,.badge-high,.badge-rejected,.badge-cancelled {{ border-color:#ef4444; color:#fca5a5; }}
    .badge-running,.badge-pending,.badge-pending_approval,.badge-awaiting_approval,.badge-cooldown,.badge-medium {{ border-color:#f59e0b; color:#fcd34d; }}
    .badge-info {{ border-color:#38bdf8; color:#7dd3fc; }}
    .nav,.filters {{ display:flex; flex-wrap:wrap; gap:10px; align-items:center; margin-top:10px; }}
    .nav a {{ background:#020617; border:1px solid var(--line); border-radius:999px; padding:8px 10px; }}
    label {{ color:var(--muted); font-size:13px; }}
    select,button {{ color:var(--text); background:#020617; border:1px solid var(--line); border-radius:9px; padding:8px 10px; }}
    button {{ cursor:pointer; }}
    ul {{ margin:0; padding-left:20px; }}
    li {{ margin:7px 0; }}
    @media (max-width:800px) {{ header {{ flex-direction:column; }} .table-wrap {{ overflow-x:auto; }} }}
  </style>
</head>
<body>
<main>
  <header>
    <div>
      <h1>Velocity Claw Dashboard v2</h1>
      <p class='muted'>Operational overview with filtered runs and direct HTML inspection of steps and artifacts.</p>
      <div class='nav'>
        <a href='/version'>version</a>
        <a href='/dashboard'>classic dashboard</a>
        <a href='/diagnostics/v2'>diagnostics v2</a>
        <a href='/ops/console'>ops console</a>
        <a href='/runs'>runs json</a>
        <a href='/approvals'>approvals json</a>
        <a href='/queue'>queue json</a>
        <a href='/metrics'>metrics json</a>
      </div>
    </div>
    <section class='card'>
      <div>Version: <b>{html_escape(__version__)}</b> <span class='muted'>({html_escape(__release_stage__)})</span></div>
      <div>Profile: <b>{html_escape(execution_profile)}</b></div>
      <div>Safe mode: <b>{html_escape(safe_mode)}</b></div>
      <div>Trusted mode: <b>{html_escape(trusted_mode)}</b></div>
    </section>
  </header>

  <div class='grid'>
    {number_card('Version', __version__)}
    {number_card('Release readiness', release_state.get('readiness', 'unknown'))}
    {number_card('Release score', release_score)}
    {number_card('Queue running', queue_summary.get('running', 0))}
    {number_card('Queue failed', queue_summary.get('failed', 0))}
    {number_card('Approvals pending', approval_summary.get('pending', len(approvals)))}
    {number_card('Risk flags', len(risk_flags))}
    {number_card('Provider failed routes', provider_summary.get('failed_routes', 0))}
  </div>

  <section class='card section'>
    <h2>Diagnostics</h2>
    {render_risk_flags(risk_flags)}
  </section>

  <section class='card section'>
    <h2>Last failed run</h2>
    {last_failed_block}
  </section>

  <section class='card section'>
    <h2>Recent runs</h2>
    <div class='filters' aria-label='Run filters'>
      <label for='run-status-filter'>Status</label>
      <select id='run-status-filter'>{status_options}</select>
      <label for='run-profile-filter'>Profile</label>
      <select id='run-profile-filter'>{profile_options}</select>
      <button type='button' id='run-filter-clear'>Clear</button>
      <span class='muted'>Visible: <b id='run-visible-count'>{len(run_rows)}</b> / {len(run_rows)}</span>
    </div>
    <div class='table-wrap'>
      <table id='runs-table'><thead><tr><th>Run ID</th><th>Task</th><th>Status</th><th>Profile</th><th>Created</th><th>Inspect</th></tr></thead><tbody>
        {''.join(run_rows)}
        {recorded_empty}
        <tr id='runs-filter-empty' hidden><td colspan='6' class='empty-state'>No runs match the selected status and profile.</td></tr>
      </tbody></table>
    </div>
  </section>

  <section class='card section'>
    <h2>Pending approvals</h2>
    <div class='table-wrap'><table><thead><tr><th>Run ID</th><th>Step</th><th>Title</th><th>Reason</th><th>Links</th></tr></thead><tbody>
      {''.join(approval_rows) or "<tr><td colspan='5' class='empty-state'>No pending approvals.</td></tr>"}
    </tbody></table></div>
  </section>

  <section class='card section'>
    <h2>Queue</h2>
    <div class='table-wrap'><table><thead><tr><th>Job ID</th><th>Task</th><th>Status</th><th>Attempts</th><th>Terminal reason</th></tr></thead><tbody>
      {''.join(queue_rows) or "<tr><td colspan='5' class='empty-state'>No queued jobs.</td></tr>"}
    </tbody></table></div>
  </section>

  <section class='card section'>
    <h2>Provider health</h2>
    <div class='table-wrap'><table><thead><tr><th>Provider</th><th>Requests</th><th>Successes</th><th>Failures</th><th>State</th><th>Last error</th></tr></thead><tbody>
      {''.join(provider_rows) or "<tr><td colspan='6' class='empty-state'>No provider health data.</td></tr>"}
    </tbody></table></div>
  </section>

  <section class='card section'>
    <h2>Raw metric counters</h2>
    <pre>{html_escape(metrics)}</pre>
  </section>
</main>
<script>
(() => {{
  const status = document.getElementById('run-status-filter');
  const profile = document.getElementById('run-profile-filter');
  const clear = document.getElementById('run-filter-clear');
  const rows = Array.from(document.querySelectorAll('.run-row'));
  const empty = document.getElementById('runs-filter-empty');
  const count = document.getElementById('run-visible-count');
  const apply = () => {{
    let visible = 0;
    rows.forEach((row) => {{
      const show = (!status.value || row.dataset.status === status.value) && (!profile.value || row.dataset.profile === profile.value);
      row.hidden = !show;
      if (show) visible += 1;
    }});
    count.textContent = String(visible);
    empty.hidden = rows.length === 0 || visible !== 0;
  }};
  status.addEventListener('change', apply);
  profile.addEventListener('change', apply);
  clear.addEventListener('click', () => {{ status.value = ''; profile.value = ''; apply(); }});
  apply();
}})();
</script>
</body>
</html>
""".strip()
