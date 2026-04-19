# VelocityClaw Symbol Navigation Spec

This document defines the first implementation target for issue #7: **Add symbol-aware code navigation**.

---

## Goal

Enable VelocityClaw to navigate code by structure instead of relying only on full-file reads and plain text search.

The symbol navigation layer should help the agent find and read:
- functions
- classes
- imports
- routes
- references

The first version can focus on Python.

---

## Why This Matters

A development agent becomes much stronger when it can work with code units directly.

Without symbol-aware navigation, the agent often has to:
- scan entire files
- rely on brittle string matching
- read too much irrelevant content
- make edits with less confidence

Symbol navigation provides a smarter bridge between planning and code editing.

---

## First Version Scope

The first version should support Python projects and cover:

### Read-only symbol operations
- find function by name
- find class by name
- find imports in a file
- read full function block
- read full class block
- return symbol location metadata

### Optional early bonus
- basic route detection for FastAPI/Flask style decorators
- simple reference search via text-based heuristics

---

## Proposed Tool Interface

### Find symbol
```json
{
  "tool": "code.find_symbol",
  "args": {
    "name": "create_plan",
    "kind": "function"
  }
}
```

### Read symbol
```json
{
  "tool": "code.read_symbol",
  "args": {
    "path": "velocity_claw/planner/planner.py",
    "name": "Planner",
    "kind": "class"
  }
}
```

### List imports
```json
{
  "tool": "code.list_imports",
  "args": {
    "path": "velocity_claw/planner/planner.py"
  }
}
```

---

## Suggested Internal Interface

```python
class CodeNavigationTool:
    def find_symbol(self, name: str, kind: str | None = None) -> list[dict]:
        ...

    def read_symbol(self, path: str, name: str, kind: str) -> dict:
        ...

    def list_imports(self, path: str) -> list[dict]:
        ...
```

---

## Required Result Shapes

### `find_symbol`
Should return a list of matches like:

```json
[
  {
    "path": "velocity_claw/planner/planner.py",
    "kind": "function",
    "name": "create_plan",
    "line_start": 21,
    "line_end": 29
  }
]
```

### `read_symbol`
Should return:

```json
{
  "path": "velocity_claw/planner/planner.py",
  "kind": "class",
  "name": "Planner",
  "line_start": 18,
  "line_end": 57,
  "source": "class Planner: ..."
}
```

### `list_imports`
Should return structured import objects rather than raw lines only.

---

## Recommended Parsing Strategy

For Python first version:

### Preferred approach
Use Python AST where practical.

Why:
- more reliable than plain regex
- easier line range extraction
- easier distinction between function/class/import nodes

### Acceptable first fallback
If AST is not enough for a sub-case, use carefully bounded text extraction for source reconstruction.

Important:
- symbol identity should not depend on loose regex alone if AST can do the job

---

## Workspace and Safety Rules

Symbol navigation must remain workspace-scoped.

Requirements:
- only inspect files inside `workspace_root`
- reject oversized files according to configured limits
- reject binary files
- fail clearly on unreadable or invalid files

This layer should be read-only in the first version.

---

## Matching Rules

### Symbol search
Support exact match first.

Recommended first behavior:
- exact name match
- optional kind filter (`function`, `class`, `import`)
- return all matches if more than one exists

The caller should decide how to handle ambiguity.

### Ambiguity
Do not silently pick one symbol if multiple matches exist.

Instead:
- return all matches
- let planner/executor choose explicitly

---

## Route Detection (Optional Early Support)

A useful early addition is route discovery for API files.

Examples:
- FastAPI decorators like `@app.get(...)`
- Flask decorators like `@app.route(...)`

Expected output:
- route path
- HTTP method if known
- handler function name
- file location

This can be implemented after core function/class support.

---

## Reference Search (Optional Later Step)

Basic reference search can begin as workspace text search plus exact symbol matching.

Examples:
- function name usage
- class instantiation
- imported symbol usage

This does not need to be perfect in the first version.

---

## Error Cases

The navigation layer should explicitly handle:

- file not found
- path outside workspace
- binary file
- parse failure
- symbol not found
- invalid kind
- ambiguous results when a single symbol was expected

No silent fallback to full-file reads unless the caller explicitly requests it.

---

## Recommended Implementation Order

### Phase 1
- add Python AST-based symbol discovery
- implement `find_symbol`
- implement `read_symbol`
- implement `list_imports`
- add tests

### Phase 2
- add line range metadata
- improve source extraction quality
- support route detection
- add tests for API-oriented files

### Phase 3
- basic reference search
- integration with patch engine and planner
- improve multi-file symbol ranking

---

## Test Plan

Minimum tests:

### Symbol discovery
- find existing function
- find existing class
- return empty result when symbol missing
- return multiple matches when ambiguous

### Symbol reading
- read function source block
- read class source block
- include line ranges
- reject invalid file paths

### Imports
- list imports from Python file
- distinguish import/from-import forms

### Safety
- reject path outside workspace
- reject binary file
- respect file size limits

---

## Success Criteria

Issue #7 is successful when VelocityClaw can:

- find functions and classes by name
- read source for a specific symbol
- list imports structurally
- stay inside workspace and safety limits
- return structured metadata usable by planner and patch engine

---

## Suggested Next Step After This Spec

Once symbol navigation works, the best integration path is:

1. use symbol lookup to find target code  
2. use patch engine to modify it  
3. use test runner to validate it  

That is the first strong development-agent loop.
