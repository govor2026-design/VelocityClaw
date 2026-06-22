# Dashboard v2 operator guide

`GET /dashboard/v2` is the primary HTML operations view for Velocity Claw.

## Run list

The Recent runs table shows:

- run id;
- task;
- status badge;
- execution profile;
- creation time;
- operator links.

The run id and the `inspect` action open the existing HTML run inspector at:

```text
/runs/<run_id>/view
```

That page exposes the run summary, step table, failures, planning and resume context, approval history, forensics, and artifact previews without requiring an operator to read raw JSON.

Structured JSON remains available through `detail v2`, `artifacts json`, `forensics`, and `report` links.

## Filters

The Recent runs table can be filtered in the browser by:

- status;
- execution profile.

Both filters are combined. The visible result counter updates immediately, and the Clear button restores the complete recent-run list.

If no run matches the selected combination, Dashboard v2 displays an explicit no-match state instead of an empty table.

## Run profile metadata

New runs persist their execution profile as a run-level metadata artifact named:

```text
run_execution_profile
```

The memory layer projects this value as `execution_profile` in both `load_run()` and `list_recent_runs()`.

Existing databases require no schema migration. Historical runs created before profile tracking are displayed as:

```text
unknown
```

## Security

All task, run id, status, profile, error, and artifact-derived values rendered by Dashboard v2 are HTML escaped.

Dashboard v2 remains protected by the same API-key middleware as other non-health production routes.
