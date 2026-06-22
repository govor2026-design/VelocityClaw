# Approval workflow

Velocity Claw pauses sensitive execution steps and requires an explicit operator decision before continuing.

## Operator endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/approvals/v2` | Risk-prioritized pending approval index |
| GET | `/approvals/v2/{run_id}/{step_id}` | Approval detail, history, artifacts, and continuation state |
| POST | `/approvals/v2/{run_id}/{step_id}/approve` | Approve and continue from the exact plan boundary |
| POST | `/approvals/v2/{run_id}/{step_id}/reject` | Reject and terminate continuation |

All endpoints except `/health` require API-key authentication in the production app.

## Approval continuation v3

Approval continuation v3 applies to the guarded Approval v2 decision endpoints.

When a pending step is approved, Velocity Claw:

1. stores the approval decision with actor, reason, and timestamp;
2. marks the run as `resuming_after_approval`;
3. loads the stored `run_plan` artifact;
4. locates the exact approved step boundary;
5. rechecks execution-profile and security policy;
6. executes the approved step without inserting a duplicate step row;
7. persists execution artifacts;
8. continues until completion, failure, or the next approval boundary;
9. writes an `approval_continuation` artifact describing the result.

## Continuation outcomes

| Status | Meaning |
| --- | --- |
| `completed` | All remaining steps completed successfully |
| `failed` | Execution or policy validation failed |
| `awaiting_approval` | A later sensitive step created a new approval boundary |
| `manual_resume_required` | The stored plan or requested step boundary could not be recovered |

Manual-resume reasons include:

- `run_plan_missing`
- `run_plan_invalid`
- `step_boundary_missing`

Failure reasons include:

- `policy_validation_failed`
- `step_execution_failed`

## Rejection behavior

A rejection:

- records the actor and reason;
- marks the step and run as `rejected`;
- stores an `approval_rejection` artifact;
- sets `continuation_allowed` to `false`;
- blocks later approve/reject attempts with `409`.

## Artifacts

Approval workflows can create these artifact types:

| Artifact type | Purpose |
| --- | --- |
| `approval` | Request and decision payloads |
| `approval_boundary` | Initial or continuation pause boundary |
| `approval_continuation` | Completed, failed, awaiting, or manual-resume outcome |
| `approval_rejection` | Terminal rejection boundary |

`GET /approvals/v2/{run_id}/{step_id}` exposes decoded continuation and rejection artifacts through:

- `continuation`
- `latest_continuation`
- `artifacts`
- `history`

## Duplicate decision protection

Approval decisions are idempotency-guarded at the workflow level. After a step has been approved or rejected, a second decision request is blocked even when the approved step has already executed and its runtime status has changed to `success` or `failed`.
