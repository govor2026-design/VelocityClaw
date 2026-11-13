from __future__ import annotations

import json
from html import escape
from typing import Any
from urllib.parse import quote, urlencode

MAX_RENDERED_CONTENT_CHARS = 200_000


def _e(value: Any) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def normalize_step_filter(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    normalized = value.strip().lower()
    if normalized == "run":
        return normalized
    if normalized.isdigit():
        return str(int(normalized))
    raise ValueError("step must be 'run' or a non-negative integer")


def filter_artifact_items(
    items: list[dict[str, Any]],
    *,
    artifact_type: str | None = None,
    step: str | None = None,
    query: str | None = None,
) -> list[dict[str, Any]]:
    normalized_type = (artifact_type or "").strip().casefold()
    normalized_step = normalize_step_filter(step)
    query_terms = [part.casefold() for part in str(query or "").split()]
    filtered: list[dict[str, Any]] = []

    for item in items:
        if normalized_type and str(item.get("artifact_type") or "").casefold() != normalized_type:
            continue
        if normalized_step == "run" and item.get("step_id") is not None:
            continue
        if normalized_step not in {None, "run"} and str(item.get("step_id")) != normalized_step:
            continue
        if query_terms:
            searchable = " ".join(
                (
                    str(item.get("name") or ""),
                    str(item.get("artifact_type") or ""),
                    str(item.get("content_preview") or ""),
                )
            ).casefold()
            if not all(term in searchable for term in query_terms):
                continue
        filtered.append(item)
    return filtered


def _explorer_url(
    run_id: Any,
    *,
    artifact_index: int | None = None,
    artifact_type: str | None = None,
    step: str | None = None,
    query: str | None = None,
) -> str:
    params: dict[str, Any] = {}
    if artifact_index is not None:
        params["artifact"] = artifact_index
    if artifact_type:
        params["type"] = artifact_type
    if step:
        params["step"] = step
    if query:
        params["q"] = query
    encoded = urlencode(params)
    suffix = f"?{encoded}" if encoded else ""
    return f"/runs/{quote(str(run_id), safe='')}/artifacts/v2/explorer{suffix}"


def render_artifact_explorer_v2(
    *,
    run: dict[str, Any],
    artifact_index: dict[str, Any],
    selected: dict[str, Any] | None = None,
    artifact_type: str | None = None,
    step: str | None = None,
    query: str | None = None,
) -> str:
    run_id = run.get("run_id")
    items = artifact_index.get("items") or []
    filtered = filter_artifact_items(
        items,
        artifact_type=artifact_type,
        step=step,
        query=query,
    )
    type_values = sorted(str(value) for value in artifact_index.get("counts_by_type", {}))
    step_values = sorted(
        {int(item["step_id"]) for item in items if item.get("step_id") is not None}
    )
    has_run_level = any(item.get("step_id") is None for item in items)

    type_options = ["<option value=''>all</option>"]
    for value in type_values:
        selected_mark = " selected" if value == artifact_type else ""
        type_options.append(
            f"<option value='{_e(value)}'{selected_mark}>{_e(value)}</option>"
        )

    step_options = ["<option value=''>all</option>"]
    if has_run_level:
        selected_mark = " selected" if step == "run" else ""
        step_options.append(f"<option value='run'{selected_mark}>run level</option>")
    for value in step_values:
        selected_mark = " selected" if step == str(value) else ""
        step_options.append(
            f"<option value='{value}'{selected_mark}>step {value}</option>"
        )

    rows = []
    for item in filtered:
        view_url = _explorer_url(
            run_id,
            artifact_index=item.get("index"),
            artifact_type=artifact_type,
            step=step,
            query=query,
        )
        rows.append(
            "<tr>"
            f"<td>{_e(item.get('index'))}</td>"
            f"<td>{_e(item.get('name'))}</td>"
            f"<td><code>{_e(item.get('artifact_type'))}</code></td>"
            f"<td>{_e(item.get('step_id') if item.get('step_id') is not None else 'run')}</td>"
            f"<td>{_e(item.get('content_size'))}</td>"
            f"<td>{_e(item.get('created_at'))}</td>"
            f"<td><a href='{_e(view_url)}'>view</a> · <a href='{_e(item.get('api_url'))}'>json</a></td>"
            "</tr>"
        )

    selected_html = "<p class='muted'>Select an artifact to inspect its full content.</p>"
    if selected:
        raw_content = str(selected.get("content") or "")
        if selected.get("is_json"):
            raw_content = json.dumps(
                selected.get("json_value"),
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        truncated = len(raw_content) > MAX_RENDERED_CONTENT_CHARS
        visible_content = raw_content[:MAX_RENDERED_CONTENT_CHARS]
        truncation_note = (
            f"<p class='warning'>Browser preview truncated at {MAX_RENDERED_CONTENT_CHARS} characters. Use the JSON endpoint for full content.</p>"
            if truncated
            else ""
        )
        selected_html = (
            "<div class='selected-meta'>"
            f"<span><b>Name:</b> {_e(selected.get('name'))}</span>"
            f"<span><b>Type:</b> <code>{_e(selected.get('artifact_type'))}</code></span>"
            f"<span><b>Step:</b> {_e(selected.get('step_id') if selected.get('step_id') is not None else 'run')}</span>"
            f"<span><b>Characters:</b> {_e(selected.get('content_size'))}</span>"
            f"<span><b>Bytes:</b> {_e(selected.get('content_size_bytes'))}</span>"
            f"<span><a href='{_e((selected.get('links') or {}).get('api'))}'>full JSON</a></span>"
            "</div>"
            f"{truncation_note}<pre class='artifact-content'>{_e(visible_content)}</pre>"
        )

    return f"""
<!doctype html>
<html lang='en'>
<head>
  <meta charset='utf-8'>
  <meta name='viewport' content='width=device-width, initial-scale=1'>
  <title>Velocity Claw Artifact Explorer</title>
  <style>
    :root {{ color-scheme:dark; --bg:#0f172a; --panel:#111827; --muted:#94a3b8; --text:#e5e7eb; --line:#263244; --accent:#38bdf8; }}
    body {{ margin:0; font-family:ui-sans-serif,system-ui,-apple-system,Segoe UI,Arial,sans-serif; background:var(--bg); color:var(--text); }}
    main {{ max-width:1400px; margin:0 auto; padding:28px; }}
    a {{ color:var(--accent); text-decoration:none; }}
    .card {{ background:var(--panel); border:1px solid var(--line); border-radius:16px; padding:18px; margin-top:16px; }}
    .muted {{ color:var(--muted); }}
    .warning {{ color:#fcd34d; }}
    form,.selected-meta {{ display:flex; flex-wrap:wrap; gap:12px; align-items:end; }}
    label {{ display:grid; gap:6px; color:var(--muted); }}
    select,input,button {{ font:inherit; color:var(--text); background:#020617; border:1px solid var(--line); border-radius:9px; padding:9px 11px; }}
    input {{ min-width:260px; }}
    .table-scroll {{ overflow-x:auto; }}
    table {{ width:100%; border-collapse:collapse; }}
    th,td {{ border-bottom:1px solid var(--line); padding:10px; text-align:left; vertical-align:top; }}
    th {{ color:var(--muted); font-size:13px; }}
    code,pre {{ background:#020617; border:1px solid var(--line); border-radius:8px; padding:4px 7px; }}
    .artifact-content {{ white-space:pre-wrap; overflow-wrap:anywhere; max-height:70vh; overflow:auto; }}
  </style>
</head>
<body><main>
  <p><a href='/dashboard/v2'>← Dashboard v2</a> · <a href='/dashboard/v2/runs?run_id={_e(run_id)}'>Run inspector</a> · <a href='/runs/{_e(run_id)}/detail/v2'>Run detail JSON</a> · <a href='/runs/{_e(run_id)}/artifacts/v2'>Artifact index JSON</a></p>
  <h1>Artifact explorer</h1>
  <p><code>{_e(run_id)}</code> — {_e(run.get('task'))}</p>
  <p class='muted'>Filtered artifacts: {_e(len(filtered))} of {_e(len(items))}</p>

  <section class='card'>
    <form method='get' action='/runs/{_e(run_id)}/artifacts/v2/explorer'>
      <label>Type<select name='type'>{''.join(type_options)}</select></label>
      <label>Step<select name='step'>{''.join(step_options)}</select></label>
      <label>Search<input type='search' name='q' maxlength='200' value='{_e(query)}' placeholder='Name, type, or preview'></label>
      <button type='submit'>Apply filters</button>
      <a href='/runs/{_e(run_id)}/artifacts/v2/explorer'>Clear</a>
    </form>
  </section>

  <section class='card'>
    <h2>Artifacts</h2>
    <div class='table-scroll'><table><thead><tr><th>#</th><th>Name</th><th>Type</th><th>Step</th><th>Characters</th><th>Created</th><th>Actions</th></tr></thead><tbody>
      {''.join(rows) or "<tr><td colspan='7'>No artifacts match the selected filters.</td></tr>"}
    </tbody></table></div>
  </section>

  <section class='card'><h2>Content</h2>{selected_html}</section>
</main></body></html>
""".strip()
