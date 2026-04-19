# VelocityClaw — 7 Day Sprint Plan

This sprint focuses on the highest-leverage improvements for turning VelocityClaw into a stronger coding agent foundation.

---

## Sprint Goal

Build the first strong end-to-end development workflow:

**code navigation -> patch edit -> diff -> test run -> parse failures -> safe dry-run support**

---

## Day 1 — Patch engine foundation

**Primary issue:** #2 Add patch-based code editing engine

### Tasks
- [ ] Define patch operation format
- [ ] Implement `insert`
- [ ] Implement `replace_block`
- [ ] Implement `append`
- [ ] Enforce workspace-safe patch apply
- [ ] Add unit tests for base patch operations

### Expected result
- The agent can modify files more precisely than full overwrite.

---

## Day 2 — Patch engine completion

**Primary issue:** #2 Add patch-based code editing engine

### Tasks
- [ ] Implement `replace_function`
- [ ] Implement `replace_class`
- [ ] Generate diff before write
- [ ] Save diff as artifact
- [ ] Handle errors:
  - [ ] block not found
  - [ ] function not found
  - [ ] ambiguous match
- [ ] Add tests for advanced patch operations

### Expected result
- Patch editing becomes useful for real code modification tasks.

---

## Day 3 — Test runner

**Primary issue:** #3 Add test runner tool

### Tasks
- [ ] Add `test.run` tool
- [ ] Support `pytest`
- [ ] Support `python -m pytest`
- [ ] Add workspace restrictions
- [ ] Add timeout handling
- [ ] Return structured result with:
  - [ ] stdout
  - [ ] stderr
  - [ ] exit code
  - [ ] summary
- [ ] Add tests for safe execution and timeout behavior

### Expected result
- The agent can run tests after code changes.

---

## Day 4 — Structured test failure parsing

**Primary issue:** #4 Parse test runner output into structured failures

### Tasks
- [ ] Implement pytest output parser
- [ ] Extract:
  - [ ] failed test name
  - [ ] file
  - [ ] line
  - [ ] assertion
  - [ ] traceback summary
- [ ] Return structured failure objects
- [ ] Add parser unit tests
- [ ] Add failure fixture examples

### Expected result
- Test failures become machine-usable instead of raw logs only.

---

## Day 5 — Symbol-aware navigation

**Primary issue:** #7 Add symbol-aware code navigation

### Tasks
- [ ] Implement symbol search for Python:
  - [ ] function
  - [ ] class
  - [ ] import
- [ ] Add `code.find_symbol`
- [ ] Add `code.read_symbol`
- [ ] Restrict navigation to workspace files
- [ ] Add tests for symbol resolution

### Expected result
- The agent can read targeted code units instead of scanning full files only.

---

## Day 6 — Dry-run mode

**Primary issue:** #5 Add dry-run execution mode

### Tasks
- [ ] Add `dry_run=true` runtime option
- [ ] Make write operations simulated:
  - [ ] fs writes
  - [ ] patch apply
  - [ ] git operations
  - [ ] shell execution
- [ ] Keep planner/security/executor trace active
- [ ] Mark simulated steps in logs and reports
- [ ] Add dry-run tests

### Expected result
- The agent can safely preview intended actions without changing the project.

---

## Day 7 — Integration flow

**Primary issues:** #2 #3 #4 #5 #7

### Tasks
- [ ] Build one end-to-end workflow:
  - [ ] find symbol
  - [ ] modify code via patch engine
  - [ ] generate diff
  - [ ] run tests
  - [ ] parse failures
- [ ] Add integration test for the full flow
- [ ] Add demo task example
- [ ] Review weak spots and fix blocker bugs

### Expected result
- The first strong developer workflow exists end-to-end.

---

## Sprint Deliverable

By the end of this sprint, VelocityClaw should be able to:

- precisely edit code
- show diffs before/after changes
- run tests
- parse test failures into structured data
- locate functions/classes/imports
- support safe dry-run execution

---

## Highest Priority Order

1. #2 Add patch-based code editing engine  
2. #3 Add test runner tool  
3. #4 Parse test runner output into structured failures  
4. #7 Add symbol-aware code navigation  
5. #5 Add dry-run execution mode  

---

## Success Metric

The sprint is successful when this demo workflow works reliably:

**Find a function -> patch it -> show diff -> run tests -> parse result -> report success or failure**
