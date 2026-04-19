# VelocityClaw Security Guide

This document describes the security model and operational safety expectations for VelocityClaw.

---

## Security Goals

VelocityClaw is designed to operate on real project files and tools, so its security model must prioritize:

- workspace isolation
- explicit execution boundaries
- predictable validation
- safe defaults
- auditable traces

The project should never rely on trust alone.

---

## Core Security Principles

### 1. Workspace Isolation
The agent must operate only inside the configured workspace.

Requirements:
- all file reads and writes stay inside `workspace_root`
- path traversal must be blocked
- system directories must be inaccessible
- relative paths must resolve safely against workspace root

Why it matters:
- file access outside the project boundary is one of the highest-risk failure modes for any local agent

---

### 2. Safe Tool Access
Every tool must be treated as a privileged boundary.

Requirements:
- shell commands must be restricted
- git commands must be limited to safe workflows
- HTTP access must be constrained by host allowlists
- file operations must validate path and size

Why it matters:
- agent power comes from tools, but tool misuse is also where most risk lives

---

### 3. Structured Validation Before Execution
The system should validate a step before executing it.

Requirements:
- planner returns structured steps
- security layer validates step inputs
- executor runs only validated actions
- failures are explicit and typed

Why it matters:
- validation after execution is too late

---

### 4. Safe Defaults
VelocityClaw should assume restrictive defaults.

Expected defaults:
- restricted shell allowlist
- restricted git commands
- no free network access
- no writes outside workspace
- no destructive operations without explicit support

Why it matters:
- safe defaults reduce damage from bad prompts, bad model outputs, and user mistakes

---

### 5. Traceability and Auditability
All important operations should be inspectable after the fact.

Requirements:
- each run has a `run_id`
- each step stores tool, args, status, result, error, timestamps
- security blocks are visible and understandable
- artifacts should preserve diffs and logs when relevant

Why it matters:
- debugging and trust both depend on being able to inspect what happened

---

## Security Boundaries by Area

### Filesystem
Protected by:
- workspace root validation
- path resolution rules
- write permission checks
- file size limits

### Shell
Protected by:
- allowlist of safe commands
- dangerous pattern blocking
- workspace-aware execution
- timeout limits

### Git
Protected by:
- safe command restrictions
- destructive command blocking
- repo-local execution only

### HTTP
Protected by:
- allowed host validation
- timeout controls
- response size limits
- structured error handling

### Planning / Models
Protected by:
- structured JSON plan schema
- no execution from raw model text alone
- provider error separation

---

## Operational Recommendations

### Use profiles
VelocityClaw should evolve toward distinct execution profiles such as:
- `safe`
- `dev`
- `owner`

This makes it easier to run the same system under different trust levels.

### Prefer dry-run first
When possible:
- preview actions first
- inspect diffs
- inspect planned shell/git steps
- then allow real execution

### Review sensitive operations
For future high-risk actions, prefer an approval workflow rather than direct execution.

---

## Non-Goals

VelocityClaw should not try to behave like an unrestricted system agent.

It is not intended to:
- freely control the whole machine
- bypass workspace rules
- execute arbitrary destructive shell commands by default
- ignore traceability in favor of convenience

---

## Recommended Next Security Improvements

Near-term security work should focus on:

1. dry-run execution mode  
2. approval workflow for sensitive operations  
3. execution profiles (`safe/dev/owner`)  
4. diff preview before writes  
5. stronger artifact-based auditing  

---

## Security Summary

VelocityClaw should remain a **bounded, inspectable, workspace-scoped agent**.

The project becomes safer when:
- planning is structured
- tools are constrained
- execution is validated
- results are logged
- dangerous actions require stronger control
