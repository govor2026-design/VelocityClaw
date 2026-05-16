from __future__ import annotations

from html import escape
from typing import Any


def html_escape(value: Any) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def status_badge(status: str) -> str:
    normalized = (status or "unknown").lower()
    return f"<span class='badge badge-{html_escape(normalized)}'>{html_escape(status or 'unknown')}</span>"


def number_card(label: str, value: Any) -> str:
    return f"<section class='card metric'><div class='label'>{html_escape(label)}</div><div class='value'>{html_escape(value)}</div></section>"


def run_links(run_id: Any) -> str:
    safe_run_id = html_escape(run_id)
    return (
        f"<a href='/runs/{safe_run_id}/detail/v2'>detail v2</a> · "
        f"<a href='/runs/{safe_run_id}/artifacts/v2'>artifacts</a> · "
        f"<a href='/runs/{safe_run_id}/forensics'>forensics</a> · "
        f"<a href='/runs/{safe_run_id}/report'>report</a> · "
        f"<a href='/runs/{safe_run_id}/view'>classic</a>"
    )


def approval_links(run_id: Any, step_id: Any) -> str:
    safe_run_id = html_escape(run_id)
    safe_step_id = html_escape(step_id)
    return (
        f"<a href='/approvals/v2/{safe_run_id}/{safe_step_id}'>review</a> · "
        f"<a href='/runs/{safe_run_id}/detail/v2'>run detail</a>"
    )


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

    run_rows = []
    for run in recent_runs:
        run_id = run.get("run_id", "")
        run_rows.append(
            "<tr>"
            f"<td><code>{html_escape(run_id)}</code></td>"
            f"<td>{html_escape(run.get('task'))}</td>"
            f"<td>{status_badge(str(run.get('status') or 'unknown'))}</td>"
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

    return f"""
<!doctype html>
<html lang='en'>
<head>
  <meta charset='utf-8'>
  <meta name='viewport' content='width=device-width, initial-scale=1'>
  <title>Velocity Claw Dashboard v2</title>
  <style>
    :root {{ color-scheme: dark; --bg:#0f172a; --panel:#111827; --muted:#94a3b8; --text:#e5e7eb; --line:#263244; --accent:#38bdf8; }}
    body {{ margin:0; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Arial, sans-serif; background:var(--bg); color:var(--text); }}
    main {{ max-width:1280px; margin:0 auto; padding:28px; }}
    header {{ display:flex; justify-content:space-between; gap:18px; align-items:flex-start; margin-bottom:24px; }}
    h1 {{ margin:0; font-size:32px; }}
    h2 {{ margin:0 0 12px; font-size:20px; }}
    a {{ color:var(--accent); text-decoration:none; }}
    .muted {{ color:var(--muted); }}
    .grid {{ display:grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap:14px; margin:18px 0; }}
    .card {{ background:var(--panel); border:1px solid var(--line); border-radius:16px; padding:16px; box-shadow:0 8px 24px rgba(0,0,0,.18); }}
    .metric .label {{ color:var(--muted); font-size:13px; }}
    .metric .value {{ font-size:26px; font-weight:700; margin-top:6px; }}
    .section {{ margin-top:18px; }}
    table {{ width:100%; border-collapse:collapse; overflow:hidden; border-radius:12px; }}
    th, td {{ border-bottom:1px solid var(--line); padding:10px; text-align:left; vertical-align:top; }}
    th {{ color:var(--muted); font-size:13px; font-weight:600; }}
    code {{ background:#020617; border:1px solid var(--line); border-radius:8px; padding:2px 6px; }}
    .badge {{ display:inline-block; border:1px solid var(--line); border-radius:999px; padding:2px 8px; font-size:12px; }}
    .badge-completed, .badge-ok, .badge-ready {{ border-color:#22c55e; color:#86efac; }}
    .badge-failed, .badge-error {{ border-color:#ef4444; color:#fca5a5; }}
    .badge-running, .badge-pending, .badge-cooldown {{ border-color:#f59e0b; color:#fcd34d; }}
    .nav {{ display:flex; flex-wrap:wrap; gap:10px; margin-top:10px; }}
    .nav a {{ background:#020617; border:1px solid var(--line); border-radius:999px; padding:8px 10px; }}
  </style>
</head>
<body>
<main>
  <header>
    <div>
      <h1>Velocity Claw Dashboard v2</h1>
      <p class='muted'>Operational overview for runs, approvals, queue, providers, and release readiness.</p>
      <div class='nav'>
        <a href='/dashboard'>classic dashboard</a>
        <a href='/ops/console'>ops console</a>
        <a href='/runs'>runs json</a>
        <a href='/approvals'>approvals json</a>
        <a href='/queue'>queue json</a>
        <a href='/metrics'>metrics json</a>
      </div>
    </div>
    <section class='card'>
      <div>Profile: <b>{html_escape(execution_profile)}</b></div>
      <div>Safe mode: <b>{html_escape(safe_mode)}</b></div>
      <div>Trusted mode: <b>{html_escape(trusted_mode)}</b></div>
    </section>
  </header>

  <div class='grid'>
    {number_card('Release readiness', release_state.get('readiness', 'unknown'))}
    {number_card('Release score', release_score)}
    {number_card('Queue running', queue_summary.get('running', 0))}
    {number_card('Queue failed', queue_summary.get('failed', 0))}
    {number_card('Approvals pending', approval_summary.get('pending', len(approvals)))}
    {number_card('Provider failed routes', provider_summary.get('failed_routes', 0))}
  </div>

  <section class='card section'>
    <h2>Last failed run</h2>
    {last_failed_block}
  </section>

  <section class='card section'>
    <h2>Recent runs</h2>
    <table><thead><tr><th>Run ID</th><th>Task</th><th>Status</th><th>Created</th><th>Links</th></tr></thead><tbody>
      {''.join(run_rows) or "<tr><td colspan='5'>No runs recorded.</td></tr>"}
    </tbody></table>
  </section>

  <section class='card section'>
    <h2>Pending approvals</h2>
    <table><thead><tr><th>Run ID</th><th>Step</th><th>Title</th><th>Reason</th><th>Links</th></tr></thead><tbody>
      {''.join(approval_rows) or "<tr><td colspan='5'>No pending approvals.</td></tr>"}
    </tbody></table>
  </section>

  <section class='card section'>
    <h2>Queue</h2>
    <table><thead><tr><th>Job ID</th><th>Task</th><th>Status</th><th>Attempts</th><th>Terminal reason</th></tr></thead><tbody>
      {''.join(queue_rows) or "<tr><td colspan='5'>No queued jobs.</td></tr>"}
    </tbody></table>
  </section>

  <section class='card section'>
    <h2>Provider health</h2>
    <table><thead><tr><th>Provider</th><th>Requests</th><th>Successes</th><th>Failures</th><th>State</th><th>Last error</th></tr></thead><tbody>
      {''.join(provider_rows) or "<tr><td colspan='6'>No provider health data.</td></tr>"}
    </tbody></table>
  </section>

  <section class='card section'>
    <h2>Raw metric counters</h2>
    <pre>{html_escape(metrics)}</pre>
  </section>
</main>
</body>
</html>
""".strip()
