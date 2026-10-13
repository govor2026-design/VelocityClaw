# VelocityClaw Issue Backlog

This document contains the prioritized development backlog for VelocityClaw.

---

## Implementation status — 2026-10-13

The original foundation backlog is **15 of 18 issues complete**. Three issues are partially complete and are not blockers for a single-owner Telegram/API deployment.

| Issue | Status | Current implementation |
| --- | --- | --- |
| 1. Dry-run mode | Complete | Runtime setting and write/patch/test simulation are covered by safety tests. |
| 2. Per-step retry policy | Partial | Provider, queue, run-resume, and auto-fix retries exist; a generic transient retry wrapper for every execution step is still missing. |
| 3. Failure classification | Partial | Queue terminal reasons and provider diagnostics exist; failed steps still lack one stable `error_type` contract across planner, executor, tool, security, and provider errors. |
| 4. Patch-based editing | Complete | Patch engine supports targeted block, function, and class operations with diffs. |
| 5. Symbol-aware navigation | Complete | Code navigation can locate and read functions, classes, imports, and references. |
| 6. Diff preview | Complete | Patch results expose unified diffs and run artifacts retain them. |
| 7. Test runner | Complete | Restricted pytest, Python pytest, and npm execution returns structured results. |
| 8. Test failure parsing | Complete | Pytest and npm failures are normalized with test, path, line, and assertion fields. |
| 9. Auto-fix loop | Complete | Bounded patch/test attempts and forensics are persisted per run. |
| 10. Project facts memory | Complete | Project facts, reusable notes, and task-aware project context persist in SQLite. |
| 11. Resume failed run | Complete | Failed-run context, retry, and approval continuation preserve trace history. |
| 12. Run artifacts | Complete | Plans, context, diffs, logs, failures, approvals, and summaries are linked to runs. |
| 13. Web dashboard | Complete | Dashboard v2 exposes runs, steps, artifacts, diagnostics, queue, and approvals. |
| 14. Approval workflow | Complete | Sensitive steps pause, approve/reject decisions are audited, and continuation is guarded. |
| 15. Execution profiles | Complete | Safe, dev, and owner profiles change tool access and are exposed through API diagnostics. |
| 16. Background workers | Partial | API jobs execute asynchronously with lifecycle controls; an optional separate worker process is not implemented. |
| 17. Queue and concurrency | Complete | Persistent queue supports limits, cancellation, retry, recovery, pause/resume, and shutdown. |
| 18. Deployment hardening | Complete | Non-root Docker/systemd paths, safe defaults, Telegram service, WAL, backups, and smoke gates are documented and tested. |

---

## Epic 1 — Core Stability

### Issue 1. Add dry-run mode
**Title:** Add dry-run execution mode

**Goal:**  
Allow the agent to build and validate plans without making real changes.

**Tasks:**  
- Add `dry_run=true` option to settings and runtime
- Make `fs.write`, `fs.append`, `fs.replace`, `git.run`, and `shell.run` simulate execution only
- Mark dry-run steps clearly in reports and logs

**Done when:**  
- dry-run mode is configurable
- no real file/system/git changes happen in dry-run
- final report shows simulated actions

**Labels:** `core`, `safety`, `P1`

---

### Issue 2. Add retry policy for steps
**Title:** Add per-step retry policy

**Goal:**  
Retry temporary execution failures safely.

**Tasks:**  
- Add configurable retry count
- Retry only model/tool/network failures
- Never retry security violations
- Store retry attempts in step metadata

**Done when:**  
- failed transient steps can retry automatically
- retry count is visible in logs and results
- security errors fail immediately

**Labels:** `core`, `executor`, `P1`

---

### Issue 3. Improve failure classification
**Title:** Add structured failure classification

**Goal:**  
Make failures easier to debug and route.

**Tasks:**  
- Add error types:
  - `planner_error`
  - `executor_error`
  - `tool_error`
  - `security_error`
  - `provider_error`
- Add `error_type` field to step results and API responses

**Done when:**  
- each failed step has structured error type
- logs and API expose failure categories

**Labels:** `core`, `logging`, `P1`

---

## Epic 2 — Code Editing

### Issue 4. Implement patch-based editing
**Title:** Add patch-based code editing engine

**Goal:**  
Support precise file editing instead of full overwrite only.

**Tasks:**  
- Add patch operations:
  - `insert`
  - `replace_block`
  - `replace_function`
  - `replace_class`
- Preserve formatting where possible
- Return diff artifacts

**Done when:**  
- agent can modify exact code regions
- file overwrites are no longer the only edit strategy

**Labels:** `agent`, `editing`, `P1`

---

### Issue 5. Add symbol-aware file navigation
**Title:** Add symbol-aware code navigation

**Goal:**  
Let the agent understand code structure better.

**Tasks:**  
- Add tools to locate:
  - functions
  - classes
  - imports
  - routes
  - references
- Support targeted reads instead of full-file reads

**Done when:**  
- agent can query symbols directly
- code navigation becomes structure-aware

**Labels:** `agent`, `tools`, `P1`

---

### Issue 6. Add diff preview before write
**Title:** Add diff preview for file modifications

**Goal:**  
Make edits inspectable before they are applied.

**Tasks:**  
- Generate unified diff before write
- Save diff as artifact
- Expose diff in API/UI

**Done when:**  
- each modification has previewable diff
- diff is attached to run artifacts

**Labels:** `editing`, `artifacts`, `P2`

---

## Epic 3 — Testing Loop

### Issue 7. Add test runner tool
**Title:** Add test runner tool

**Goal:**  
Allow the agent to verify code changes automatically.

**Tasks:**  
- Add support for:
  - `pytest`
  - `python -m pytest`
  - `npm test`
- Add safe timeouts and workspace restrictions
- Return structured output

**Done when:**  
- agent can run tests from executor
- results are stored as structured step output

**Labels:** `tools`, `tests`, `P1`

---

### Issue 8. Parse test failures
**Title:** Parse test runner output into structured failures

**Goal:**  
Make test errors machine-usable by the agent.

**Tasks:**  
- Extract:
  - failed test name
  - file
  - line
  - assertion/message
- Normalize test output into structured data

**Done when:**  
- raw logs are parsed into useful failure objects
- agent can use them in follow-up repair steps

**Labels:** `tests`, `parser`, `P1`

---

### Issue 9. Add auto-fix loop after failed tests
**Title:** Add auto-fix loop for failed tests

**Goal:**  
Let the agent try limited self-repair after test failures.

**Tasks:**  
- Add fix loop with max attempts
- Re-run tests after each fix
- Store all attempts in run history

**Done when:**  
- agent can iteratively repair simple failures
- loop is bounded and traceable

**Labels:** `agent`, `tests`, `P2`

---

## Epic 4 — Memory and Traceability

### Issue 10. Add project facts memory
**Title:** Add project facts memory layer

**Goal:**  
Persist important knowledge about each project.

**Tasks:**  
- Store:
  - framework
  - entrypoints
  - project commands
  - code style conventions
  - repo-specific notes
- Load facts at run start

**Done when:**  
- project facts persist across runs
- agent can reuse learned repo context

**Labels:** `memory`, `agent`, `P2`

---

### Issue 11. Add resume failed run
**Title:** Add resume support for failed runs

**Goal:**  
Resume work from last failed execution state.

**Tasks:**  
- Track restartable failed runs
- Resume from last valid step
- Preserve trace continuity

**Done when:**  
- failed run can be resumed safely
- resumed execution remains tied to the same trace history

**Labels:** `memory`, `core`, `P2`

---

### Issue 12. Store artifacts for every run
**Title:** Expand artifact storage per run

**Goal:**  
Keep useful outputs attached to runs.

**Tasks:**  
- Save:
  - diffs
  - test logs
  - model outputs
  - summaries
- Expose artifacts via API

**Done when:**  
- each run can expose artifacts cleanly
- artifacts are linked to `run_id`

**Labels:** `memory`, `artifacts`, `P2`

---

## Epic 5 — UX / Product Layer

### Issue 13. Build minimal web dashboard
**Title:** Add minimal web dashboard for runs

**Goal:**  
Provide a visual interface for monitoring executions.

**Tasks:**  
- Add pages:
  - run list
  - run details
  - step trace
  - artifacts/errors
- Use current API as backend

**Done when:**  
- users can inspect runs from browser
- step-by-step execution is visible

**Labels:** `ui`, `dashboard`, `P1`

---

### Issue 14. Add approval workflow for dangerous steps
**Title:** Add approval workflow for sensitive operations

**Goal:**  
Require explicit approval for higher-risk actions.

**Tasks:**  
- Add `pending_approval` state
- Allow approve/reject actions
- Log reviewer decision

**Done when:**  
- dangerous steps can pause for approval
- approval decisions are stored and auditable

**Labels:** `security`, `ui`, `P2`

---

### Issue 15. Add execution profiles
**Title:** Add execution profiles: safe/dev/owner

**Goal:**  
Make runtime behavior configurable by trust level.

**Tasks:**  
- Add profiles:
  - `safe`
  - `dev`
  - `owner`
- Tie profile to available tools and security policy

**Done when:**  
- profile changes real execution limits
- profile is exposed in settings/API

**Labels:** `security`, `config`, `P2`

---

## Epic 6 — Infrastructure

### Issue 16. Add background run workers
**Title:** Add background execution workers

**Goal:**  
Move long runs out of request/response path.

**Tasks:**  
- Add worker process mode
- Make API submit jobs asynchronously
- Add polling/status endpoints

**Done when:**  
- long runs do not block API
- runs can execute in background workers

**Labels:** `infra`, `workers`, `P2`

---

### Issue 17. Add run queue and concurrency control
**Title:** Add run queue and concurrency limits

**Goal:**  
Control parallel execution safely.

**Tasks:**  
- Add queued/running/completed states
- Add configurable concurrency limit
- Handle cancellation safely

**Done when:**  
- concurrent runs are limited and predictable
- queue state is visible

**Labels:** `infra`, `core`, `P2`

---

### Issue 18. Harden deployment configuration
**Title:** Harden deployment and runtime isolation

**Goal:**  
Improve deployment safety and runtime isolation.

**Tasks:**  
- Keep non-root execution
- Improve workspace isolation
- Clean env defaults
- Improve deployment docs
- Keep safe defaults in Docker/Compose

**Done when:**  
- deployment is cleaner and safer
- docs match actual runtime expectations

**Labels:** `infra`, `security`, `P2`

---

## Top 5 Priority Issues

1. **Add stable structured failure classification**
2. **Add generic per-step transient retry policy**
3. **Run the production smoke suite on the target host**
4. **Observe API and Telegram together under real workload**
5. **Evaluate pending dependency upgrades individually**

---

## Suggested Label Set

- `core`
- `security`
- `agent`
- `tools`
- `ui`
- `infra`
- `memory`
- `tests`
- `artifacts`
- `P1`
- `P2`
- `P3`

---

## Suggested Next Move

For the personal-agent deployment, use this order:

1. publish and deploy `0.3.0`
2. run the version and runtime-safety smoke gates on the target host
3. confirm the backup timer creates restorable memory and queue copies
4. operate API and Telegram for a short soak period
5. implement structured errors and per-step retry only after observing real failure patterns

An external worker process is optional for a single-owner installation and should be added only when process isolation or higher throughput is actually required.
