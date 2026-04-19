# VelocityClaw Approval Workflow Spec

This document defines the first implementation target for issue #13: **Add approval workflow for sensitive operations**.

---

## Goal

Introduce a controlled approval workflow for sensitive or higher-risk agent actions.

The first version should allow VelocityClaw to pause execution when a step is considered sensitive, and require an explicit user decision before proceeding.

---

## Why This Matters

Even with strong security defaults, some actions are still important enough to require human confirmation.

Examples:
- risky file modifications
- broad multi-file edits
- git operations with wider impact
- future network-sensitive or deployment-sensitive actions

Approval workflow improves:
- trust
- operational safety
- visibility
- product maturity

---

## First Version Scope

The first version should support:

- step-level approval decisions
- pause-before-execution behavior
- approve / reject actions
- run and step state updates
- clear audit trail for each approval decision

### Not required yet
- multi-user approval chains
- team review routing
- advanced role-based permissions
- time-based escalation

Those can come later.

---

## Core Workflow

### Normal flow
1. planner generates structured steps
2. security layer or policy marks a step as sensitive
3. executor does **not** execute the step immediately
4. step enters `pending_approval`
5. user approves or rejects
6. execution continues or stops accordingly

---

## What Counts as Sensitive

The first version should use explicit policy rules to classify a step as sensitive.

Recommended examples:
- broad write operations
- high-impact patch operations
- git operations beyond basic read-only inspection
- future publish/deploy-type steps
- future network actions outside very narrow safe defaults

Important:
- sensitivity classification should be explicit and auditable
- not based on vague hidden heuristics alone

---

## Proposed Data Model

```json
{
  "step_id": 4,
  "title": "Apply patch to planner.py",
  "tool": "fs.patch",
  "status": "pending_approval",
  "approval": {
    "required": true,
    "reason": "multi-line code modification",
    "decision": null,
    "decided_by": null,
    "decided_at": null
  }
}
```

### Approval fields
- `required`
- `reason`
- `decision`
- `decided_by`
- `decided_at`
- `decision_note` (optional later)

---

## Suggested Internal Interface

```python
class ApprovalManager:
    def requires_approval(self, step: dict) -> bool:
        ...

    def build_approval_record(self, step: dict, reason: str) -> dict:
        ...

    def approve(self, run_id: str, step_id: int, actor: str) -> dict:
        ...

    def reject(self, run_id: str, step_id: int, actor: str) -> dict:
        ...
```

---

## Required States

The workflow needs explicit state transitions.

### Step states
- `pending_approval`
- `approved`
- `rejected`
- `running`
- `completed`
- `failed`

### Run behavior
If a step is pending approval:
- run should pause cleanly
- later continuation should resume from that step

This integrates naturally with future resume support.

---

## API Requirements

The approval workflow should expose API endpoints or equivalent operations for:

- list pending approvals
- approve step
- reject step
- inspect approval reason and context

Minimum expected data returned:
- run id
- step id
- tool
- title
- reason for approval requirement
- current decision state

---

## Dashboard / UI Expectations

The dashboard should later show:
- pending approval badge
- step title and tool
- approval reason
- approve button
- reject button
- approval decision history

The first implementation does not need a polished UI, but it should prepare for this surface.

---

## Audit Requirements

Every approval decision should be logged.

Minimum required audit data:
- run id
- step id
- decision
- actor
- timestamp
- reason for approval requirement

This is important for trust and debugging.

---

## Safety Rules

Approval workflow should never weaken the existing security model.

Important rules:
- approval does not bypass path validation
- approval does not bypass workspace rules
- approval does not silently override security policy failures
- approval only allows a step that is otherwise valid but classified as sensitive

This is critical.

Approval is for **sensitive-but-allowed** actions, not for invalid or blocked actions.

---

## Rejection Behavior

If a step is rejected:
- the step should move to `rejected`
- the run should stop or transition to a clear halted state
- the final report should explain that execution stopped due to rejection

No hidden fallthrough to execution.

---

## Recommended Classification Strategy

The first version should keep classification simple.

Suggested initial policy examples:
- require approval for patch operations affecting multiple files
- require approval for class/function replacements beyond a configurable size
- require approval for future git write operations
- require approval for future deployment/publish actions

This keeps the feature useful without making every step annoying.

---

## Recommended Implementation Order

### Phase 1
- add `pending_approval` state
- add approval record storage
- add approve/reject operations
- pause run on approval-required step
- add tests

### Phase 2
- add API support
- add dashboard rendering hooks
- add audit history view
- improve sensitivity classification rules

### Phase 3
- integrate execution profiles
- add configurable approval policies
- support more advanced approval logic if needed

---

## Test Plan

Minimum tests:

### Core state handling
- sensitive step becomes `pending_approval`
- approved step resumes execution
- rejected step stops execution

### Audit
- approval decision is stored
- actor and timestamp are stored
- reason is preserved

### Safety
- approval cannot override blocked security violation
- invalid steps still fail normally
- only sensitive valid steps enter approval flow

### Integration
- executor pauses correctly
- run state remains traceable
- approval integrates with memory and dashboard/API data

---

## Success Criteria

Issue #13 is successful when VelocityClaw can:

- detect approval-required steps
- pause before execution
- accept approve/reject decisions
- log approval decisions clearly
- resume or stop execution predictably

---

## Suggested Next Step After This Spec

Once approval workflow exists, the strongest next integrations are:

1. issue #6 — dashboard support for approvals  
2. issue #14 — execution profiles  
3. issue #12 — richer artifacts and audit traces  

That path turns approval into a real operational safety layer.
