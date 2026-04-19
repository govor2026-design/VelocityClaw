# VelocityClaw Auto-Fix Loop Spec

This document defines the first implementation target for issue #9: **Add auto-fix loop for failed tests**.

---

## Goal

Enable VelocityClaw to attempt limited, traceable self-repair after test failures.

The auto-fix loop should connect existing or planned components into a bounded workflow:

**find target -> patch code -> run tests -> parse failures -> attempt fix -> repeat within limits**

---

## Why This Matters

Once VelocityClaw can:
- navigate symbols
- edit code
- run tests
- parse failures

…the next major capability is self-repair.

A bounded auto-fix loop turns the agent from a simple executor into a practical development assistant that can iterate on small bugs and failed tests.

---

## First Version Scope

The first version should support:

- one task context
- one or more failed tests
- limited repair attempts
- explicit retry/fix limits
- full traceability of every attempt

The first version should **not** try to be fully autonomous or unbounded.

---

## Core Workflow

### Initial run
1. apply or generate code change
2. run tests
3. parse failures

### Repair loop
4. identify likely failure target
5. plan fix step
6. patch code
7. re-run tests
8. parse results
9. repeat until success or stop condition

---

## Required Constraints

The loop must remain bounded.

### Required limits
- maximum number of repair attempts
- timeout per test run
- timeout per overall loop
- no retries after security violation
- no infinite planning/editing cycles

Recommended first default:
- `max_fix_attempts = 2` or `3`

---

## Proposed Data Model

```json
{
  "run_id": "...",
  "mode": "auto_fix",
  "max_attempts": 3,
  "attempts": [
    {
      "attempt": 1,
      "reason": "test failure",
      "target_symbols": ["create_plan"],
      "patches": [...],
      "test_result": {...},
      "status": "failed"
    }
  ]
}
```

### Core fields
- `mode`
- `max_attempts`
- `attempts`
- `reason`
- `target_symbols`
- `patches`
- `test_result`
- `status`

---

## Suggested Internal Interface

```python
class AutoFixLoop:
    async def run(self, task: str, context: dict | None = None) -> dict:
        ...
```

### Supporting methods
```python
async def attempt_fix(self, failure_data: dict) -> dict:
    ...

async def rerun_tests(self, target: str | None = None) -> dict:
    ...

async def should_continue(self, state: dict) -> bool:
    ...
```

---

## Required Inputs

The auto-fix loop depends on these components:

### Must exist first
- patch engine
- test runner
- structured test failure parsing
- symbol-aware navigation

### Strongly recommended
- artifact storage
- diff preview
- dry-run support

---

## Stop Conditions

The loop must stop when any of these conditions is reached:

- tests pass
- max attempts reached
- security violation occurs
- no valid fix target found
- repeated identical failure with no meaningful change
- patch application fails in a non-recoverable way
- overall loop timeout reached

This is critical to keep behavior safe and predictable.

---

## Failure Handling Rules

### Allowed to retry
- failed test assertions
- parseable code-level breakage
- limited test failures tied to specific symbols or files

### Not allowed to retry automatically
- security policy violations
- path violations
- shell/git restrictions
- unsupported tools
- ambiguous patch targets with no clear selection

This keeps the loop from turning into uncontrolled thrashing.

---

## Traceability Requirements

Each attempt should store:

- attempt number
- reason for retry
- target file or symbol
- generated diff
- patch summary
- test result summary
- parsed failures
- status
- timestamps

This data should be attached to the same run or a linked repair sub-trace.

---

## Diff and Artifact Requirements

Each repair attempt should preserve:

- diff before apply
- diff after apply if relevant
- raw test output
- parsed failure objects
- loop summary

This is important both for debugging and for future approval workflows.

---

## Planner / Reasoning Expectations

The auto-fix loop should not replan the entire world on every attempt.

A good first version should:
- focus only on the current failure set
- narrow scope to likely files/symbols
- prefer small targeted edits
- avoid large broad changes unless explicitly instructed

This keeps repairs practical and contained.

---

## Safety Rules

The loop must obey all existing system boundaries:

- workspace-only operations
- validated patch application
- validated test execution
- bounded attempts
- no destructive shell/git escalation
- no free-form uncontrolled retries

A self-repair loop should be safer than a free-form autonomous loop, not looser.

---

## Recommended Implementation Order

### Phase 1
- define loop state model
- connect failure parsing to retry trigger
- add bounded `max_attempts`
- run targeted patch -> test -> parse cycle
- add tests

### Phase 2
- improve retry decision logic
- detect repeated identical failures
- store richer artifacts and summaries
- improve symbol targeting

### Phase 3
- integrate approval mode for risky repairs
- support dry-run preview of repair attempts
- improve route/file-specific targeting

---

## Test Plan

Minimum tests:

### Loop control
- stops when tests pass
- stops at max attempts
- stops on security violation
- stops on missing valid target

### Traceability
- stores attempt count
- stores diffs and test results
- stores parsed failures per attempt

### Repair behavior
- retries after parseable failure
- does not retry after policy block
- does not loop forever on unchanged failure

### Integration
- works with patch engine
- works with test runner
- works with failure parser
- stores state in memory or artifacts

---

## Success Criteria

Issue #9 is successful when VelocityClaw can:

- detect failed tests
- attempt a bounded code repair
- re-run tests after each attempt
- stop safely on success or limit conditions
- preserve a full repair trace

---

## Suggested Next Step After This Spec

Once the auto-fix loop works, the most useful next upgrades are:

1. issue #8 — diff preview for file modifications  
2. issue #10 — project facts memory layer  
3. issue #13 — approval workflow for sensitive operations  

That path strengthens both repair quality and operational safety.
