# VelocityClaw Patch Engine Spec

This document defines the first implementation target for issue #2: **Add patch-based code editing engine**.

---

## Goal

Enable VelocityClaw to modify code and text files more safely and precisely than full file overwrite.

The patch engine should let the agent:
- insert text
- replace a block
- append text
- replace a function
- replace a class
- produce a diff artifact before applying changes

---

## Why This Matters

Today, full-file overwrite is too coarse for a development agent.

A patch engine provides:
- more precise edits
- lower risk of unintended file damage
- better diffs
- better future approval workflows
- a foundation for real code refactoring flows

---

## First Version Scope

The first version should support these operations:

### 1. `insert`
Insert text at a specified anchor.

### 2. `replace_block`
Replace a known exact block of text.

### 3. `append`
Append content to the end of a file.

### 4. `replace_function`
Replace a function body or full function block in Python files.

### 5. `replace_class`
Replace a class block in Python files.

---

## Proposed Data Model

```json
{
  "op": "replace_block",
  "path": "velocity_claw/planner/planner.py",
  "target": "old text block",
  "replacement": "new text block"
}
```

### Core fields
- `op` — operation type
- `path` — workspace-relative file path
- `target` — text or symbol to match
- `replacement` — replacement content
- `anchor` — optional insertion anchor
- `position` — optional placement hint

---

## Suggested Internal Interface

```python
class PatchEngine:
    def apply(self, patch: dict) -> dict:
        ...

    def preview(self, patch: dict) -> dict:
        ...
```

### Preview result should include
- resolved file path
- operation type
- whether the target matched
- generated diff
- whether execution is safe to apply

### Apply result should include
- operation type
- path
- changed: true/false
- diff
- error if failed

---

## Safety Rules

Patch engine must follow all existing security rules:

- path must stay inside `workspace_root`
- file must pass file size rules
- binary files must be rejected
- ambiguous symbol matches should fail explicitly
- missing target should fail explicitly
- dry-run mode must be supported

Patch engine should never silently write when the requested target is not clearly matched.

---

## Diff Requirements

Every patch operation should generate a diff before apply.

Minimum requirement:
- unified diff format
- original path
- before/after context

Diffs should later be stored as artifacts.

---

## Error Cases

The engine should explicitly handle:

- file not found
- path outside workspace
- target block not found
- function not found
- class not found
- ambiguous match
- file too large
- binary file
- empty replacement when not allowed

No silent partial success.

---

## Python-Specific Symbol Replacement

For first Python support, the engine may begin with a simple parser strategy:

- detect `def name(` for function replacement
- detect `class Name(` or `class Name:` for class replacement
- replace the full indented block

This version does not need full AST rewriting yet, but it must be predictable.

Later versions can move to AST-based replacement.

---

## Recommended Implementation Order

### Phase 1
- `insert`
- `replace_block`
- `append`
- diff preview
- tests

### Phase 2
- `replace_function`
- `replace_class`
- Python block detection
- tests

### Phase 3
- artifact integration
- dry-run integration
- executor integration
- API exposure

---

## Test Plan

Minimum tests:

### Base operations
- insert into existing file
- replace exact block
- append to file
- no write when target missing

### Safety
- reject path outside workspace
- reject binary file
- reject oversized file

### Python symbol replacement
- replace function successfully
- replace class successfully
- fail on missing function
- fail on ambiguous symbol

### Diff
- preview returns diff
- apply returns diff
- dry-run returns preview without write

---

## Success Criteria

Issue #2 is successful when VelocityClaw can:

- modify files without full overwrite only
- preview diffs before write
- fail clearly on ambiguous or unsafe edits
- support Python function/class replacement in a predictable way
- integrate safely with the existing executor and security model

---

## Suggested Next Step After This Spec

Once the patch engine base works, the project should immediately connect it to:

1. issue #3 — test runner  
2. issue #4 — structured test failure parsing  
3. issue #7 — symbol-aware navigation  

That combination creates the first real coding workflow.
