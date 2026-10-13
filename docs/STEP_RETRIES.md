# Automatic step retries

Velocity Claw can repeat a failed execution step when the executor explicitly
marks the failure as temporary and the tool is safe to invoke again.

## Configuration

| Variable | Default | Meaning |
| --- | ---: | --- |
| `STEP_MAX_RETRIES` | `1` | Maximum additional attempts after the first failure (`0` disables automatic step retries). |
| `STEP_RETRY_BACKOFF_MS` | `250` | Linear delay before each retry. Attempt 1 waits one interval, attempt 2 waits two intervals, and so on. |

Both prefixed names, such as `VELOCITY_CLAW_STEP_MAX_RETRIES`, and the
unprefixed names are supported. The prefixed value takes precedence.

## Safety contract

A step is retried only when both conditions are true:

1. The executor marks the concrete failure as transient, such as a provider
   request failure, network client failure, or timeout.
2. The tool is read-only or otherwise safe to repeat.

Safe tools include model analysis, HTTP GET, repository inspection, file and
symbol reads, patch preview, and test execution. HTTP POST, filesystem writes,
patch application, shell commands, and git commands are never retried
automatically because a failed call may already have produced a side effect.

Policy denials, security violations, invalid inputs, unknown tools, invalid
provider responses, and failed tests stop immediately.

## Observability

Every invocation is persisted as its own step record with an increasing
`attempt_no`. The immediate task response also exposes `retry_count`, while run
detail and forensic responses expose the complete attempt history and identify
retried step IDs. Retry decisions are written to the operator log.

Retries during failed-run resume continue the existing attempt sequence rather
than replacing prior records.
