from __future__ import annotations

from html import escape
from typing import Any
from urllib.parse import urlencode

from velocity_claw.api.dashboard_filters import compact_step_inspector, filter_runs, run_profile
from velocity_claw.api.dashboard_v2 import status_badge


def _e(value: Any) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def _option(value: str, selected: str | None) -> str:
    mark = " selected" if selected == value else ""
    return f"<option value='{_e(value)}'{mark}>{_e(value or 'all')}</option>"


def _run_link(run_id: Any, label: str, *, status: str | None, profile: str | None) -> str:
    params = {"run_id": str(run_id)}
    if status:
        params["status"] = status
    if profile:
        params["profile"] = profile
    return f"<a href='/dashboard/v2/runs?{urlencode(params)}'>{_e(label)}</a>"


def render_dashboard_runs_v2(
    *,
    runs: list[dict[str, Any]],
    status: str | None = None,
    profile: str | None = None,
    selected_run: dict[str, Any] | None = None,
) -> str:
    filtered = filter_runs(runs, status=status, profile=profile)
    inspector = compact_step_inspector(selected_run)

    rows = []
    for run in filtered:
        run_id = run.get("run_id")
        rows.append(
            "<tr>"
            f"<td><code>{_e(run_id)}</code></td>"
            f"<td>{_e(run.get('task'))}</td>"
            f"<td>{status_badge(str(run.get('status') or 'unknown'))}</td>"
            f"<td>{_e(run_profile(run) or 'unknown')}</td>"
            f"<td>{_e(run.get('created_at'))}</td>"
            f"<td>{_run_link(run_id, 'inspect', status=status, profile=profile)} · "
            f"<a href='/runs/{_e(run_id)}/detail/v2'>detail</a> · "
            f"<a href='/runs/{_e(run_id)}/artifacts/v2'>artifacts</a></td>"
            "</tr>"
        )

    inspector_html = "<p class='muted'>Select a run to inspect its steps.</p>"
    if inspector:
        step_rows = []
        for step in inspector["steps"]:
            step_rows.append(
                "<tr>"
                f"<td>{_e(step.get('id'))}</td>"
                f"<td>{_e(step.get('title'))}</td>"
                f"<td><code>{_e(step.get('tool'))}</code></td>"
                f"<td>{status_badge(str(step.get('status') or 'unknown'))}</td>"
                f"<td>{_e(step.get('error') or '')}</td>"
                f"<td><pre>{_e(step.get('result_preview') or '')}</pre></td>"
                "</tr>"
            )
        inspector_html = (
            f"<p><code>{_e(inspector['run_id'])}</code> — {_e(inspector['task'])} "
            f"{status_badge(str(inspector.get('status') or 'unknown'))}</p>"
            f"<p class='muted'>Profile: {_e(inspector.get('profile') or 'unknown')} · "
            f"Steps: {_e(inspector['step_count'])} · Artifacts: {_e(inspector['artifact_count'])}</p>"
            "<table><thead><tr><th>ID</th><th>Title</th><th>Tool</th><th>Status</th><th>Error</th><th>Result preview</th></tr></thead><tbody>"
            f"{''.join(step_rows) or '<tr><td colspan=\'6\'>No steps recorded.</td></tr>'}"
            "</tbody></table>"
            f"<p><a href='/runs/{_e(inspector['run_id'])}/detail/v2'>Open full run detail</a> · "
            f"<a href='/runs/{_e(inspector['run_id'])}/artifacts/v2'>Open artifact index</a></p>"
        )

    return f"""
<!doctype html>
<html lang='en'>
<head>
  <meta charset='utf-8'>
  <meta name='viewport' content='width=device-width, initial-scale=1'>
  <title>Velocity Claw Runs Inspector</title>
  <style>
    :root {{ color-scheme:dark; --bg:#0f172a; --panel:#111827; --muted:#94a3b8; --text:#e5e7eb; --line:#263244; --accent:#38bdf8; }}
    body {{ margin:0; font-family:ui-sans-serif,system-ui,-apple-system,Segoe UI,Arial,sans-serif; background:var(--bg); color:var(--text); }}
    main {{ max-width:1400px; margin:0 auto; padding:28px; }}
    a {{ color:var(--accent); text-decoration:none; }}
    .card {{ background:var(--panel); border:1px solid var(--line); border-radius:16px; padding:16px; margin-top:18px; }}
    .muted {{ color:var(--muted); }}
    form {{ display:flex; flex-wrap:wrap; gap:12px; align-items:end; }}
    label {{ display:grid; gap:6px; color:var(--muted); }}
    select,button {{ background:#020617; color:var(--text); border:1px solid var(--line); border-radius:8px; padding:8px 10px; }}
    table {{ width:100%; border-collapse:collapse; }}
    th,td {{ border-bottom:1px solid var(--line); padding:10px; text-align:left; vertical-align:top; }}
    th {{ color:var(--muted); font-size:13px; }}
    code,pre {{ background:#020617; border:1px solid var(--line); border-radius:8px; padding:2px 6px; }}
    pre {{ white-space:pre-wrap; max-width:480px; margin:0; }}
    .badge {{ display:inline-block; border:1px solid var(--line); border-radius:999px; padding:2px 8px; font-size:12px; }}
    .badge-completed,.badge-ok,.badge-ready {{ border-color:#22c55e; color:#86efac; }}
    .badge-failed,.badge-error {{ border-color:#ef4444; color:#fca5a5; }}
    .badge-running,.badge-pending,.badge-paused,.badge-pending_approval {{ border-color:#f59e0b; color:#fcd34d; }}
  </style>
</head>
<body><main>
  <p><a href='/dashboard/v2'>← Dashboard v2</a></p>
  <h1>Runs and steps inspector</h1>
  <p class='muted'>Filtered runs: {_e(len(filtered))} of {_e(len(runs))}</p>
  <section class='card'>
    <form method='get' action='/dashboard/v2/runs'>
      <label>Status<select name='status'>{_option('', status)}{''.join(_option(item, status) for item in ['running','completed','failed','cancelled','paused','pending_approval'])}</select></label>
      <label>Profile<select name='profile'>{_option('', profile)}{''.join(_option(item, profile) for item in ['safe','dev','owner'])}</select></label>
      <button type='submit'>Apply filters</button>
      <a href='/dashboard/v2/runs'>Clear</a>
    </form>
  </section>
  <section class='card'>
    <h2>Runs</h2>
    <table><thead><tr><th>Run ID</th><th>Task</th><th>Status</th><th>Profile</th><th>Created</th><th>Actions</th></tr></thead><tbody>
      {''.join(rows) or "<tr><td colspan='6'>No runs match the selected filters.</td></tr>"}
    </tbody></table>
  </section>
  <section class='card'><h2>Step inspector</h2>{inspector_html}</section>
</main></body></html>
""".strip()
