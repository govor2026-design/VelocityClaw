# Velocity Claw API guide

This guide lists the operational API endpoints exposed by Velocity Claw.

All routes except `GET /health` require API authentication when the production app wrapper is used.

Supported authentication headers:

```text
X-API-Key: <key>
Authorization: Bearer <key>
```

Configure one of these variables before exposing the API:

```bash
VELOCITY_CLAW_API_KEY=change-this-long-random-key
# or
API_KEY=change-this-long-random-key
```

## Smoke test after deployment

After starting a deployed API service, run:

```bash
VELOCITY_CLAW_API_KEY=<key> python scripts/smoke_api.py --base-url http://127.0.0.1:8000
```

The smoke script checks public health, protected-route auth behavior, authenticated status/metrics/diagnostics/runs/approvals/profile endpoints, release readiness, and Dashboard v2.

## Health and runtime status

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/health` | Public service health and metrics snapshot |
| GET | `/status` | Agent runtime status |
| GET | `/metrics` | Metrics counters |
| GET | `/diagnostics` | Classic diagnostics snapshot |
| GET | `/diagnostics/v2` | Diagnostics v2 runtime summary with risk flags |
| GET | `/ops/console` | Compact operations console snapshot |
| GET | `/dashboard` | Classic HTML dashboard |
| GET | `/dashboard/v2` | Dashboard v2 HTML overview |

Example:

```bash
curl http://127.0.0.1:8000/health
curl -H "X-API-Key: $VELOCITY_CLAW_API_KEY" http://127.0.0.1:8000/dashboard/v2
curl -H "X-API-Key: $VELOCITY_CLAW_API_KEY" http://127.0.0.1:8000/diagnostics/v2
```

## Task execution

| Method | Endpoint | Purpose |
| --- | --- | --- |
| POST | `/task` | Run a task immediately |
| POST | `/modes/run` | Run a task through a named mode |
| GET | `/modes` | List available modes |
| POST | `/auto-fix` | Run auto-fix loop for a target test |

Example:

```bash
curl -X POST http://127.0.0.1:8000/task \
  -H "X-API-Key: $VELOCITY_CLAW_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"task":"Analyze repository structure"}'
```

## Queue

| Method | Endpoint | Purpose |
| --- | --- | --- |
| POST | `/queue/submit` | Submit a queued task |
| GET | `/queue` | List queued jobs |
| GET | `/queue/{job_id}` | Get one queued job |
| POST | `/queue/{job_id}/cancel` | Cancel a queued job |
| POST | `/queue/{job_id}/requeue` | Requeue a job |

## Runs and artifacts

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/runs` | List recent runs |
| GET | `/runs/{run_id}` | Raw run payload |
| GET | `/runs/{run_id}/view` | Classic HTML run view |
| GET | `/runs/{run_id}/detail/v2` | Structured compact run summary |
| GET | `/runs/{run_id}/artifacts` | Legacy artifact grouping |
| GET | `/runs/{run_id}/artifacts/v2` | Structured artifact index |
| GET | `/runs/{run_id}/forensics` | Run forensics |
| GET | `/runs/{run_id}/report` | Run report |
| GET | `/runs/{run_id}/planning-context` | Planning context artifact |
| GET | `/runs/{run_id}/resume-context` | Resume context artifact |
| GET | `/runs/{run_id}/approval-history` | Approval history for a run |

Run detail v2 returns:

- compact run metadata
- step index
- failed steps
- pending approval steps
- artifact counts by type
- artifact grouping by type and step
- artifact previews
- approval history count
- forensic highlights
- links to related views

Example:

```bash
curl -H "X-API-Key: $VELOCITY_CLAW_API_KEY" \
  http://127.0.0.1:8000/runs/<run_id>/detail/v2
```

## Approvals

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/approvals` | List pending approvals |
| POST | `/approvals/explain` | Explain whether a step requires approval |
| POST | `/approvals/{run_id}/{step_id}/approve` | Legacy approve endpoint |
| POST | `/approvals/{run_id}/{step_id}/reject` | Legacy reject endpoint |
| GET | `/approvals/v2/{run_id}/{step_id}` | Approval v2 detail before decision |
| POST | `/approvals/v2/{run_id}/{step_id}/approve` | Guarded Approval v2 approve |
| POST | `/approvals/v2/{run_id}/{step_id}/reject` | Guarded Approval v2 reject |

Approval v2 detail returns:

- run id
- run task
- step payload
- current step status
- `can_decide`
- approval history for that step
- step artifacts
- approve/reject links

Approval v2 blocks duplicate decisions. If a step is already approved or rejected, the v2 decision endpoints return `409`.

Example:

```bash
curl -H "X-API-Key: $VELOCITY_CLAW_API_KEY" \
  http://127.0.0.1:8000/approvals/v2/<run_id>/<step_id>

curl -X POST http://127.0.0.1:8000/approvals/v2/<run_id>/<step_id>/approve \
  -H "X-API-Key: $VELOCITY_CLAW_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"actor":"owner","reason":"reviewed and approved"}'
```

## Execution profiles and security explanation

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/profiles` | List profiles |
| GET | `/profiles/active` | Active profile capability matrix |
| GET | `/profiles/explain/{tool_name}` | Explain tool access under the active profile |
| POST | `/approvals/explain` | Explain approval requirement for a step |

For tools with dots, replace `.` with `__` in the URL path.

Example:

```bash
curl -H "X-API-Key: $VELOCITY_CLAW_API_KEY" \
  http://127.0.0.1:8000/profiles/explain/shell__run
```

The profile explanation includes:

- allowed/blocked state
- tool category
- risk level
- required capability
- reason
- approval hint
- active profile capabilities

## Providers and repository context

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/providers/health` | Provider health state |
| GET | `/providers/observability` | Provider routing observability |
| GET | `/git/summary` | Safe git repository summary |
| GET | `/memory/context` | Repository memory context |
| GET | `/memory/resume?task=...` | Resume context for a task |
| GET | `/release/readiness` | Release readiness report |

## Dashboard workflow

Recommended operator flow:

1. Open `/dashboard/v2`.
2. Review recent runs and pending approvals.
3. Open `/diagnostics/v2` when troubleshooting runtime state.
4. Open `/runs/{run_id}/detail/v2` for compact run context.
5. Open `/runs/{run_id}/artifacts/v2` for artifact grouping and previews.
6. Open `/approvals/v2/{run_id}/{step_id}` before approving or rejecting.
7. Use the guarded Approval v2 decision endpoints.

## Error behavior

Common response patterns:

| Status | Meaning |
| --- | --- |
| 401 | Missing or wrong API key |
| 404 | Requested run/job/approval was not found |
| 409 | Approval decision blocked because the step is no longer pending |
| 503 | API key is not configured on protected routes |
