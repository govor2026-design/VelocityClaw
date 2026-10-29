from __future__ import annotations

import json
from html import escape
from typing import Any

from velocity_claw.api.dashboard_v2 import status_badge


def _e(value: Any) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def _json(value: Any) -> str:
    return _e(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def render_approval_review_v2(detail: dict[str, Any]) -> str:
    step = detail.get("step") or {}
    record = detail.get("approval_record") or {}
    links = detail.get("links") or {}
    can_decide = bool(detail.get("can_decide"))
    disabled = "" if can_decide else " disabled"

    history_rows = []
    for event in detail.get("history") or []:
        history_rows.append(
            "<tr>"
            f"<td>{_e(event.get('created_at'))}</td>"
            f"<td>{status_badge(str(event.get('decision') or 'unknown'))}</td>"
            f"<td>{_e(event.get('actor') or '')}</td>"
            f"<td>{_e(event.get('reason') or '')}</td>"
            "</tr>"
        )

    continuation_rows = []
    for event in detail.get("continuation") or []:
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        continuation_rows.append(
            "<tr>"
            f"<td>{_e(event.get('created_at'))}</td>"
            f"<td>{status_badge(str(payload.get('status') or event.get('artifact_type') or 'unknown'))}</td>"
            f"<td>{_e(payload.get('reason') or '')}</td>"
            f"<td>{_e(payload.get('executed_count', ''))}</td>"
            f"<td>{_e(payload.get('boundary_step_id') or payload.get('failed_step_id') or '')}</td>"
            "</tr>"
        )

    decision_hint = (
        "Review the exact tool arguments and continuation context before deciding."
        if can_decide
        else f"This step cannot be decided: {detail.get('reason') or 'not pending approval'}."
    )

    return f"""
<!doctype html>
<html lang='en'>
<head>
  <meta charset='utf-8'>
  <meta name='viewport' content='width=device-width, initial-scale=1'>
  <title>Velocity Claw Approval Review</title>
  <style>
    :root {{ color-scheme:dark; --bg:#0f172a; --panel:#111827; --muted:#94a3b8; --text:#e5e7eb; --line:#263244; --accent:#38bdf8; --ok:#22c55e; --danger:#ef4444; }}
    body {{ margin:0; font-family:ui-sans-serif,system-ui,-apple-system,Segoe UI,Arial,sans-serif; background:var(--bg); color:var(--text); }}
    main {{ max-width:1180px; margin:0 auto; padding:28px; }}
    a {{ color:var(--accent); text-decoration:none; }}
    .card {{ background:var(--panel); border:1px solid var(--line); border-radius:16px; padding:18px; margin-top:16px; }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:14px; }}
    .muted {{ color:var(--muted); }}
    .table-scroll {{ overflow-x:auto; }}
    table {{ width:100%; border-collapse:collapse; }}
    th,td {{ border-bottom:1px solid var(--line); padding:10px; text-align:left; vertical-align:top; }}
    th {{ color:var(--muted); font-size:13px; }}
    code,pre {{ background:#020617; border:1px solid var(--line); border-radius:8px; padding:4px 7px; }}
    pre {{ white-space:pre-wrap; overflow-wrap:anywhere; max-height:420px; overflow:auto; }}
    label {{ display:grid; gap:6px; margin-top:12px; color:var(--muted); }}
    input,textarea,button {{ font:inherit; color:var(--text); background:#020617; border:1px solid var(--line); border-radius:9px; padding:10px; }}
    textarea {{ min-height:90px; resize:vertical; }}
    .actions {{ display:flex; flex-wrap:wrap; gap:10px; margin-top:14px; }}
    button {{ cursor:pointer; font-weight:700; }}
    button:disabled {{ cursor:not-allowed; opacity:.45; }}
    .approve {{ border-color:var(--ok); color:#86efac; }}
    .reject {{ border-color:var(--danger); color:#fca5a5; }}
    .badge {{ display:inline-block; border:1px solid var(--line); border-radius:999px; padding:2px 8px; font-size:12px; }}
    .badge-approved,.badge-completed,.badge-success,.badge-ok {{ border-color:var(--ok); color:#86efac; }}
    .badge-rejected,.badge-failed,.badge-error {{ border-color:var(--danger); color:#fca5a5; }}
    .badge-pending_approval,.badge-requested,.badge-awaiting_approval,.badge-manual_resume_required {{ border-color:#f59e0b; color:#fcd34d; }}
  </style>
</head>
<body><main>
  <p><a href='/dashboard/v2'>← Dashboard v2</a> · <a href='{_e(links.get('run_detail_v2'))}'>Run detail</a> · <a href='{_e(links.get('api_detail'))}'>JSON detail</a></p>
  <h1>Approval review</h1>
  <p class='muted'>{_e(decision_hint)}</p>

  <section class='card grid'>
    <div><span class='muted'>Run</span><p><code>{_e(detail.get('run_id'))}</code></p></div>
    <div><span class='muted'>Run status</span><p>{status_badge(str(detail.get('run_status') or 'unknown'))}</p></div>
    <div><span class='muted'>Step</span><p><code>{_e(detail.get('step_id'))}</code> — {_e(step.get('title'))}</p></div>
    <div><span class='muted'>Current status</span><p>{status_badge(str(detail.get('current_status') or 'unknown'))}</p></div>
    <div><span class='muted'>Run profile</span><p><code>{_e(detail.get('execution_profile') or 'unknown')}</code></p></div>
    <div><span class='muted'>Approval profile</span><p><code>{_e(record.get('profile') or 'unknown')}</code></p></div>
    <div><span class='muted'>Risk</span><p>{status_badge(str(record.get('risk_level') or 'unknown'))}</p></div>
  </section>

  <section class='card'>
    <h2>{_e(detail.get('task'))}</h2>
    <p><b>Tool:</b> <code>{_e(step.get('tool'))}</code></p>
    <p><b>Reason:</b> {_e(record.get('reason') or '')}</p>
    <p><b>Operator hint:</b> {_e(record.get('operator_hint') or '')}</p>
    <p><b>Next step:</b> {_e(record.get('next_step_hint') or '')}</p>
    <h3>Arguments</h3><pre>{_json(step.get('args') or {})}</pre>
    <h3>Approval summary</h3><pre>{_json(record.get('summary') or {})}</pre>
    <h3>Triggers</h3><pre>{_json(record.get('triggers') or [])}</pre>
  </section>

  <section class='card'>
    <h2>Decision</h2>
    <label>Actor<input id='actor' maxlength='100' value='owner'></label>
    <label>Reason<textarea id='reason' maxlength='2000' placeholder='What was reviewed and why'></textarea></label>
    <div class='actions'>
      <button class='approve decision' data-url='{_e(links.get('approve'))}' data-decision='approve'{disabled}>Approve and continue</button>
      <button class='reject decision' data-url='{_e(links.get('reject'))}' data-decision='reject'{disabled}>Reject and stop</button>
    </div>
    <p id='decision-status' class='muted' aria-live='polite'></p>
    <pre id='decision-output'>No decision submitted.</pre>
  </section>

  <section class='card'>
    <h2>Decision history</h2>
    <div class='table-scroll'><table><thead><tr><th>Time</th><th>Decision</th><th>Actor</th><th>Reason</th></tr></thead><tbody>
      {''.join(history_rows) or "<tr><td colspan='4'>No approval history.</td></tr>"}
    </tbody></table></div>
  </section>

  <section class='card'>
    <h2>Continuation history</h2>
    <div class='table-scroll'><table><thead><tr><th>Time</th><th>Status</th><th>Reason</th><th>Executed</th><th>Boundary</th></tr></thead><tbody>
      {''.join(continuation_rows) or "<tr><td colspan='5'>No continuation events.</td></tr>"}
    </tbody></table></div>
  </section>

  <script>
    const buttons = Array.from(document.querySelectorAll('.decision'));
    const statusNode = document.getElementById('decision-status');
    const outputNode = document.getElementById('decision-output');
    for (const button of buttons) {{
      button.addEventListener('click', async () => {{
        const decision = button.dataset.decision;
        if (!window.confirm(`Confirm ${{decision}} for this step?`)) return;
        buttons.forEach(item => item.disabled = true);
        statusNode.textContent = `Submitting ${{decision}}…`;
        try {{
          const response = await fetch(button.dataset.url, {{
            method: 'POST',
            credentials: 'same-origin',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{
              actor: document.getElementById('actor').value.trim() || 'owner',
              reason: document.getElementById('reason').value.trim() || null,
            }}),
          }});
          const payload = await response.json();
          outputNode.textContent = JSON.stringify(payload, null, 2);
          statusNode.textContent = response.ok ? 'Decision saved. Reloading current state…' : `Decision failed (HTTP ${{response.status}}).`;
          if (response.ok) window.setTimeout(() => window.location.reload(), 1200);
        }} catch (error) {{
          outputNode.textContent = String(error);
          statusNode.textContent = 'Decision request failed.';
          buttons.forEach(item => item.disabled = false);
        }}
      }});
    }}
  </script>
</main></body></html>
""".strip()
