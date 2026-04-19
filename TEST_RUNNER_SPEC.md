# VelocityClaw Test Runner Spec

This document defines the first implementation target for issue #3: **Add test runner tool**.

---

## Goal

Enable VelocityClaw to run tests safely inside the workspace and return structured results that can be used by later reasoning and repair steps.

The test runner should become the verification layer for code changes.

---

## Why This Matters

A coding agent is much more useful when it can validate its own edits.

Without a test runner, VelocityClaw can change code but cannot reliably answer:
- did the change work?
- what failed?
- what should be fixed next?

The test runner is the foundation for:
- post-edit validation
- structured failure analysis
- auto-fix loops
- artifact collection

---

## First Version Scope

The first version should support:

### Supported commands
- `pytest`
- `python -m pytest`

Optional later:
- `npm test`
- framework-specific test commands

### Core capabilities
- run tests inside `workspace_root`
- enforce timeout limits
- capture stdout/stderr/exit code
- return structured result object
- preserve raw output for artifacts and debugging

---

## Proposed Tool Interface

```json
{
  "tool": "test.run",
  "args": {
    "runner": "pytest",
    "target": "tests/test_tools.py",
    "timeout": 120
  }
}
```

### Core fields
- `runner` — test system to use
- `target` — optional file/module/path target
- `timeout` — execution timeout in seconds
- `args` — optional extra safe arguments

---

## Suggested Internal Interface

```python
class TestRunnerTool:
    def run(self, runner: str, target: str | None = None, timeout: int = 120, extra_args: list[str] | None = None) -> dict:
        ...
```

---

## Required Result Shape

The tool should return a structured object like:

```json
{
  "runner": "pytest",
  "target": "tests/test_tools.py",
  "code": 0,
  "status": "passed",
  "stdout": "...",
  "stderr": "...",
  "duration_ms": 1832,
  "summary": {
    "passed": 8,
    "failed": 0,
    "errors": 0,
    "skipped": 0
  }
}
```

### Minimum required fields
- `runner`
- `target`
- `code`
- `status`
- `stdout`
- `stderr`
- `duration_ms`
- `summary`

---

## Safety Rules

The test runner must follow all existing security rules.

### Required protections
- execution only inside `workspace_root`
- controlled allowlist of test commands
- timeout must always apply
- no arbitrary shell expansion
- no unsafe external command injection

### Important restriction
The test runner should execute only through a safe command model, not through free-form shell strings.

---

## Status Mapping

Recommended status mapping:

- `passed` -> exit code 0 and no failures
- `failed` -> tests ran but one or more tests failed
- `error` -> command error, timeout, or invalid runner
- `timeout` -> execution exceeded configured limit

This keeps result handling predictable for later automation.

---

## Timeout Rules

Timeout handling must be explicit.

### Requirements
- every run has a timeout
- timeout must terminate execution cleanly
- timeout result must be distinguishable from test failure
- timeout details should be visible in the result and logs

---

## Summary Extraction

Even before full structured failure parsing, the first version should extract a basic summary.

### For pytest, try to capture
- passed count
- failed count
- error count
- skipped count
- total duration if available

If parsing fails, the tool should still return raw output and a best-effort status.

---

## Artifact Expectations

The test runner should later integrate with artifacts.

Recommended artifact outputs:
- raw stdout
- raw stderr
- parsed summary
- future parsed failure objects

This keeps runs inspectable and useful for dashboard/debugging.

---

## Error Cases

The tool should explicitly handle:

- unsupported runner
- target outside workspace
- timeout exceeded
- command execution failure
- missing test tool in environment
- malformed extra args

Errors should be structured and never silently downgraded.

---

## Recommended Implementation Order

### Phase 1
- add `test.run`
- support `pytest`
- support `python -m pytest`
- capture stdout/stderr/code/duration
- add timeout support
- add tests

### Phase 2
- extract basic summary counts
- improve error typing
- save artifacts
- connect to executor

### Phase 3
- prepare handoff into issue #4 failure parsing
- add support for more runners if needed

---

## Test Plan

Minimum tests:

### Safe execution
- run pytest successfully inside workspace
- reject unsupported runner
- reject invalid target outside workspace

### Result shape
- return structured result fields
- return passed status on success
- return failed status on test failure
- return timeout status on timeout

### Stability
- preserve stdout/stderr correctly
- preserve exit code correctly
- preserve duration

### Integration
- executor can dispatch `test.run`
- result can be stored in memory

---

## Success Criteria

Issue #3 is successful when VelocityClaw can:

- run tests safely inside the workspace
- return structured test results
- distinguish pass/fail/error/timeout clearly
- capture enough information for later failure parsing
- integrate cleanly with executor and memory

---

## Suggested Next Step After This Spec

Once the test runner base works, the next immediate step should be:

**issue #4 — Parse test runner output into structured failures**

That is what turns test execution into a real automated repair workflow.
