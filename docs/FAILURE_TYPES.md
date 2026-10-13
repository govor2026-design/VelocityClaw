# Failure types

Velocity Claw records a stable machine-readable `error_type` alongside the
human-readable `error` message for failed execution steps.

## Contract

| `error_type` | Meaning |
| --- | --- |
| `policy_denied` | The active execution profile or runtime policy denied the action. |
| `security_violation` | Security validation rejected a path, command, URL, or git action. |
| `provider_not_configured` | A requested model provider is unavailable because configuration is missing. |
| `provider_request_failed` | A configured provider could not complete the request. |
| `provider_response_invalid` | A provider returned an empty or structurally invalid response. |
| `planning_failed` | Planning output could not be produced or validated. |
| `test_failed` | A test runner completed with a non-passing result. |
| `tool_not_found` | A plan referenced an unregistered tool. |
| `tool_input_invalid` | Tool arguments failed validation. |
| `tool_timeout` | A tool exceeded its execution timeout. |
| `tool_execution_failed` | A registered tool failed during execution. |
| `internal_error` | An unexpected failure occurred outside a known boundary. |

The values are defined in `velocity_claw.failures.FailureType`. New values may
be added, but existing values are not repurposed.

## Surfaces

- Step results and `POST /task` step responses expose `error_type`.
- SQLite step records persist `error_type`; existing databases are migrated
  automatically.
- Run details and forensic summaries expose the failed step type.
- Provider route attempts expose provider-specific failure types.
- Planning failures are persisted as a synthetic `planner` step before the
  original exception crosses the API boundary.

Successful, approval-pending, and legacy step records use `null`. Consumers
must use `error_type` for routing and `error` only for operator diagnostics.
The category does not by itself declare whether an action is safe to retry.
