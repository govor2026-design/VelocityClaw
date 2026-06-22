# Queue persistence v2

Velocity Claw stores queue jobs in SQLite and restores them when the API process restarts.

## Startup recovery

At startup, persisted jobs are loaded. A job left in `running` is considered interrupted because its original worker is gone. It is changed to `queued`, its worker markers are cleared, recovery metadata is recorded, and it is scheduled again through the current worker pool.

The recovery history reason is `recovered_after_restart_from_running`.

## Stored job state

Each job stores its task, context, status, result, error, attempt count, worker slot, terminal reason, timestamps, recovery count, and lifecycle history.

The queue database uses the configured memory database path with the `.queue` suffix.

## Lifecycle

Normal transitions are:

- `queued` to `running` to `completed`;
- `running` to `failed` when the runner raises an error;
- `queued` or `running` to `cancelled` after operator cancellation;
- `failed` or `cancelled` to `queued` after requeue.

Terminal reasons include `runner_completed`, `runner_exception`, `cancelled_by_operator`, `max_attempts_exhausted`, and `invalid_persisted_status`.

A cancelled running job remains cancelled even when the underlying runner finishes later. The late result is discarded.

## Retry behavior

Use `POST /queue/v2/{job_id}/requeue` to retry a failed or cancelled job. The job is immediately scheduled after it returns to `queued`.

When the attempt limit is reached, the endpoint returns `409 max_attempts_exhausted`. An explicit operator retry can use `force=true`. Completed jobs cannot be requeued.

## Operator endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/queue/v2/runtime` | Inspect counts, workers, limits, persistence, and startup recovery |
| POST | `/queue/v2/recover` | Schedule all queued jobs without duplicate worker tasks |
| POST | `/queue/v2/{job_id}/requeue` | Requeue and schedule a failed or cancelled job |
| POST | `/queue/v2/{job_id}/cancel` | Cancel a queued or running job |

Legacy queue endpoints remain available for compatibility.

## Duplicate scheduling protection

Scheduled and active job IDs are tracked separately. Repeated recovery calls do not create duplicate worker tasks for the same job.

## Diagnostics

`GET /diagnostics/v2` includes queue counts, active and scheduled workers, retry limits, persistence state, startup recovery details, and recovery-related risk flags.
