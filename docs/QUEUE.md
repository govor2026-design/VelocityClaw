# Queue persistence and worker orchestration v2

Velocity Claw stores queue jobs in SQLite and runs them through a bounded asynchronous worker orchestrator.

## Runtime model

The orchestrator tracks explicit task handles instead of creating an unbounded number of coroutines that wait on a semaphore.

At most `QUEUE_MAX_CONCURRENCY` jobs are scheduled at one time. When one worker finishes, the oldest remaining queued job is scheduled automatically. This keeps memory use predictable while preserving FIFO execution order.

Each active job receives the lowest available deterministic worker slot, such as `slot-1` or `slot-2`. Slots are released when a job completes, fails, or is cancelled.

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

Terminal reasons include `runner_completed`, `runner_exception`, `cancelled_by_operator`, `worker_task_cancelled`, `max_attempts_exhausted`, and `invalid_persisted_status`.

Cancelling a scheduled or running job cancels its tracked `asyncio.Task`. A cancelled runner cannot overwrite the persisted terminal state with a late result.

## Pause, resume, drain, and shutdown

`pause` stops new worker scheduling without changing queued jobs or interrupting active workers.

`resume` enables scheduling and immediately fills available worker capacity from the oldest queued jobs.

`drain` pauses scheduling and waits up to the requested timeout for currently tracked workers. It does not cancel active work. Jobs that were not yet scheduled stay queued until resume.

Application shutdown stops accepting work, cancels tracked runners, waits up to `QUEUE_SHUTDOWN_TIMEOUT_SECONDS`, and persists cancellation state before the API process exits.

## Retry behavior

Use `POST /queue/v2/{job_id}/requeue` to retry a failed or cancelled job. The job is immediately scheduled when the orchestrator is accepting work and has capacity. Otherwise it remains queued and is picked up automatically when capacity becomes available or the queue is resumed.

When the attempt limit is reached, the endpoint returns `409 max_attempts_exhausted`. An explicit operator retry can use `force=true`. Completed jobs cannot be requeued.

## Runtime settings

All settings support the `VELOCITY_CLAW_` prefix and the legacy short name.

| Setting | Default | Purpose |
| --- | ---: | --- |
| `QUEUE_MAX_CONCURRENCY` | `2` | Maximum tracked and active worker tasks |
| `QUEUE_MAX_ATTEMPTS` | `3` | Maximum attempts before normal requeue is blocked |
| `QUEUE_RECOVER_ON_STARTUP` | `true` | Recover interrupted persisted work at startup |
| `QUEUE_SHUTDOWN_TIMEOUT_SECONDS` | `10` | Maximum graceful shutdown wait |

## Operator endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/queue/v2/runtime` | Inspect counts, tracked tasks, worker slots, limits, persistence, and recovery |
| POST | `/queue/v2/recover` | Fill available capacity from queued jobs without duplicates |
| POST | `/queue/v2/pause` | Stop new scheduling while current workers continue |
| POST | `/queue/v2/resume` | Resume scheduling and fill worker capacity |
| POST | `/queue/v2/drain?timeout_seconds=10` | Pause and wait for tracked workers without cancelling them |
| POST | `/queue/v2/{job_id}/requeue` | Requeue and schedule a failed or cancelled job |
| POST | `/queue/v2/{job_id}/cancel` | Cancel a queued or running job and interrupt its task |

Legacy queue endpoints remain available for compatibility. New operator workflows should use `/queue/v2/*`.

## Duplicate scheduling protection

Tracked task handles, scheduled IDs, and active IDs are checked before a job is scheduled. Repeated recovery or resume calls do not create duplicate worker tasks for the same job.

## Diagnostics

`GET /diagnostics/v2` includes:

- accepting/paused state;
- tracked, scheduled, and active worker counts;
- deterministic active slot mapping;
- available and scheduling capacity;
- retry limits and persistence state;
- startup recovery details;
- a `queue_not_accepting_work` information flag while paused or draining.
