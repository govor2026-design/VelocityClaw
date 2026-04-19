# VelocityClaw Dashboard Spec

This document defines the first implementation target for issue #6: **Add minimal web dashboard for runs**.

---

## Goal

Provide a minimal but useful browser-based dashboard for inspecting VelocityClaw runs.

The first version should make it easy to:
- see recent runs
- inspect step traces
- review errors
- review artifacts and diffs
- understand what the agent actually did

---

## Why This Matters

VelocityClaw already has CLI and API entry points, but a dashboard makes the system much easier to operate and trust.

Without a UI, users must piece together state from logs and raw API output.

A dashboard improves:
- observability
- debugging
- trust in agent actions
- product feel
- future approval workflows

---

## First Version Scope

The first version should be intentionally minimal.

### Required pages
1. run list
2. run details
3. step trace
4. artifacts/errors view

### Not required yet
- authentication
- multi-user features
- background worker control panels
- full admin settings

Those can come later.

---

## Core User Flows

### Flow 1 — Inspect recent runs
A user opens the dashboard and sees recent runs with:
- run id
- task summary
- status
- created time
- completed time

### Flow 2 — Open a run
A user clicks a run and sees:
- task
- run status
- summary
- steps
- errors
- artifacts

### Flow 3 — Inspect a step
A user expands a step and sees:
- step id
- title
- tool
- args
- status
- result or error
- timestamps

---

## Suggested UI Structure

### Page 1 — Runs
Main table/list of recent runs.

Recommended columns:
- run id
- task
- status
- created at
- completed at

### Page 2 — Run Details
Detailed view for a single run.

Recommended sections:
- run summary
- step timeline
- errors
- artifacts

### Page 3 — Step Details
Detailed section or panel for one step.

Recommended fields:
- title
- tool
- args
- result
- error
- timing

### Page 4 — Artifact View
Artifact panel for:
- diffs
- test logs
- model output summaries
- raw step outputs if needed

---

## API Dependencies

The dashboard should use the existing API as its backend.

Minimum expected data sources:
- list runs
- get run by id
- get step details
- get artifacts for run

If endpoints are not yet complete, the dashboard spec should guide which API additions are needed.

---

## Suggested Frontend Approach

Keep first version simple.

Recommended options:
- server-rendered templates with FastAPI
- or a minimal frontend layer over FastAPI endpoints

The first version does not need a heavy frontend stack.

Priority should be:
- readability
- fast implementation
- easy debugging
- easy deployment

---

## Required Data Display

### Run-level
- run id
- task text
- status
- created/completed timestamps
- final summary

### Step-level
- step id
- title
- tool
- args
- status
- result
- error
- started/completed timestamps

### Artifact-level
- artifact name
- artifact type if available
- artifact content preview

---

## Status Display Rules

Use clear visual status categories:
- running
- completed
- failed
- blocked
- pending approval (future)

The first version should make failed and running states especially easy to spot.

---

## Error Display Rules

Errors should be readable.

Recommended behavior:
- show concise error summary first
- allow expansion for raw detail
- clearly identify which step failed
- show tool and args used for that step

This is more useful than dumping raw trace output into one block.

---

## Artifact Display Rules

Artifacts should be inspectable without clutter.

Recommended first approach:
- show artifact list in sidebar or section
- click to expand content
- support plain text first
- support diff view later

The first version only needs enough structure to make artifacts useful.

---

## Safety / Product Considerations

Even the first dashboard should respect product safety goals.

### Required considerations
- do not expose unsafe execution shortcuts just for convenience
- do not turn the dashboard into a free-form shell panel
- keep the dashboard read-heavy in the first version
- write/approve controls can come after visibility is solid

This keeps the first UI simple and trustworthy.

---

## Recommended Implementation Order

### Phase 1
- add recent runs page
- add run detail page
- add step detail rendering
- add basic error display

### Phase 2
- add artifact view
- improve status display
- add filtering or search
- improve empty/error states

### Phase 3
- add diff rendering
- add approval workflow hooks
- add future worker/job state views

---

## Test Plan

Minimum tests:

### Backend/API integration
- recent runs endpoint returns data expected by dashboard
- run detail endpoint returns steps and summary
- missing run returns clear error state

### UI rendering
- run list renders empty and non-empty states
- failed step renders clearly
- artifacts render when available

### Safety and reliability
- dashboard handles malformed or partial data gracefully
- dashboard does not crash on missing artifacts or errors

---

## Success Criteria

Issue #6 is successful when VelocityClaw has a browser-accessible dashboard that lets a user:

- view recent runs
- inspect a single run
- inspect steps and errors
- review artifacts
- understand what the agent did without reading raw logs directly

---

## Suggested Next Step After This Spec

Once the dashboard exists, the strongest follow-up is:

1. issue #12 — store artifacts for every run  
2. issue #13 — approval workflow for sensitive operations  
3. issue #14 — execution profiles  

That path turns the dashboard into a real operational control surface.
