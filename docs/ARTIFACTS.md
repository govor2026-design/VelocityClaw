# Artifact explorer

Velocity Claw stores plans, logs, diffs, failures, approval records, resume
boundaries, and other run evidence as SQLite artifacts.

## Operator routes

| Route | Purpose |
| --- | --- |
| `GET /runs/{run_id}/artifacts/v2` | JSON index grouped by type and step |
| `GET /runs/{run_id}/artifacts/v2/items/{artifact_index}` | Full content for one artifact |
| `GET /runs/{run_id}/artifacts/v2/explorer` | Browser explorer for a run |

The explorer supports these query parameters:

- `type` — exact artifact type;
- `step` — a non-negative step ID or `run` for run-level artifacts;
- `q` — case-insensitive multi-term search over name, type, and preview;
- `artifact` — artifact index to open in the content panel.

Filter state is preserved when an artifact is opened. JSON artifacts are
pretty-printed in the browser. All names, metadata, and contents are HTML
escaped before rendering.

## Large artifacts

The HTML content panel is capped at 200,000 characters to keep the operator
page responsive. A truncation notice links to the authenticated item endpoint,
which returns the complete persisted content together with character and UTF-8
byte counts.

Artifact indices are stable within a run because artifacts are loaded in their
SQLite insertion order. An index outside the selected run returns
`artifact_not_found` instead of exposing another run's content.
