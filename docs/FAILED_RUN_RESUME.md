# Failed-run resume v2

Velocity Claw can continue a failed run inside the original trace instead of creating a new run and repeating all completed work.

## Behavior

A failed-run resume:

- keeps the original `run_id`;
- loads the persisted `run_plan`;
- finds the first step whose latest attempt is still `failed`;
- skips earlier completed steps;
- retries the failed step and then executes the remaining plan;
- reuses the persisted planning context;
- uses the execution profile stored on the original run;
- passes every resumed step through the normal profile, runtime, approval, and security guard;
- stores every retry as a new step-attempt record;
- preserves the previous failed attempt for forensics;
- records resume boundary and summary artifacts.

Resume is rejected when:

- the run does not exist;
- the run status is not `failed`;
- the persisted plan is missing or invalid;
- no effective failed step can be located;
- another resume for the same run is already active in the process.

## API

### Preview

```text
GET /runs/{run_id}/resume/v2
```

The preview returns:

- the failed step and plan index;
- steps that will be skipped;
- steps that remain;
- stored execution profile;
- next resume number;
- next attempt number for the failed step;
- whether a resume is already active.

### Execute

```text
POST /runs/{run_id}/resume/v2
Content-Type: application/json

{
  "actor": "operator",
  "reason": "dependency was repaired"
}
```

The endpoint may return:

- `completed` — all resumed steps succeeded;
- `failed` — a resumed step failed again;
- `awaiting_approval` — a resumed step opened a new approval boundary.

One approval applies only to the gated step. Later approval-gated steps pause again.

## Step attempts

The `steps` table is migrated in place with:

- `attempt_no` — attempt number for that plan step;
- `phase` — `initial` or `failed_resume`.

Historical rows receive `attempt_no=1` and `phase=initial`.

`MemoryStore.load_run()` preserves all attempt records. Run forensics and reports calculate the current effective state from the latest attempt for each `step_id`, while keeping older failures visible in attempt history.

Run detail v2 exposes:

- effective step status;
- total attempt records;
- attempt history grouped by step;
- retried step IDs;
- resume boundaries and summaries;
- the resume endpoint link.

## Approval continuation

When a resumed step requires approval:

1. a `pending_approval` attempt is stored with `phase=failed_resume`;
2. Approval v2 resolves the latest attempt for that `step_id`;
3. approval does not change the stored run profile;
4. the step is validated and executed through the standard guard;
5. execution continues from the approval boundary.

Approval cannot override a profile deny, disabled runtime capability, invalid path, blocked URL, disallowed command, or unsafe git operation.

## Resume versus retry

Use failed-run **resume** when the persisted plan remains valid and completed work should be retained.

Use the existing **retry** workflow when the task needs a new plan or materially different context. Retry creates a new run; resume continues the original run.
