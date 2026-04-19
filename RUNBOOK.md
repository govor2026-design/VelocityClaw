# VelocityClaw Runbook

This runbook describes how to operate, verify, and troubleshoot VelocityClaw in day-to-day use.

---

## Purpose

Use this document when you need to:

- start the project
- verify core functionality
- inspect recent runs
- debug failures
- validate safety behavior
- understand what to check after changes

---

## Basic Startup Paths

### CLI mode
Use CLI when testing local task execution.

Typical use cases:
- run one task
- test planner/executor flow
- inspect logs quickly

### API mode
Use API when integrating with other tools or building a dashboard.

Typical use cases:
- submit tasks programmatically
- inspect run status
- review structured responses

### Telegram mode
Use Telegram only after core logic is stable enough for external entry points.

Typical use cases:
- remote interaction
- lightweight control surface
- notifications and simple commands

---

## Before Running

Check these first:

- workspace path is correct
- settings and environment variables are loaded
- model provider configuration is valid
- shell and git settings match intended safety level
- memory database path is writable

Recommended first checks:
- health endpoint works
- dry-run or safe tasks work
- no path validation regressions exist

---

## Safe Smoke Test Flow

Use this order after important changes:

1. run a safe planning-only task  
2. run a workspace-local file read task  
3. run a simulated write or dry-run task  
4. run a controlled patch/edit workflow  
5. run tests  

Why this order:
- it catches configuration and policy problems before more complex execution paths

---

## What to Inspect After a Run

After each significant run, inspect:

- run status
- step list
- failed step, if any
- tool used
- args passed
- result or error
- timestamps
- artifacts, if generated

A healthy run should be easy to trace from start to finish.

---

## Common Failure Types

### Planner failure
Symptoms:
- invalid plan format
- non-JSON response
- missing step fields

What to check:
- model router output
- planner prompt format
- JSON validation path

### Security failure
Symptoms:
- blocked path
- blocked URL
- blocked shell/git command

What to check:
- workspace_root
- allowed hosts
- shell/git restrictions
- active security profile

### Executor failure
Symptoms:
- tool dispatch error
- missing args
- unsupported tool

What to check:
- plan step schema
- executor handlers
- returned step metadata

### Provider failure
Symptoms:
- provider not configured
- HTTP/provider request errors
- invalid model response

What to check:
- provider keys
- routing order
- fallback logic
- network connectivity

### Memory / trace failure
Symptoms:
- missing steps in run history
- incomplete metadata
- malformed stored artifacts

What to check:
- save_step payload
- serialization of args/result/error
- run loading logic

---

## Recommended Debug Order

When something breaks, debug in this order:

1. confirm workspace and settings  
2. confirm planner output shape  
3. confirm security validation  
4. confirm executor tool dispatch  
5. confirm memory persistence  
6. confirm API output shape  

This keeps debugging aligned with the actual system flow.

---

## Operational Best Practices

- prefer safe tasks first after code changes
- test new tools with unit tests before integration use
- inspect diffs before trusting file modifications
- keep logs structured and readable
- avoid enabling broad shell/network capabilities without clear need
- use future approval workflow for sensitive actions

---

## Recommended Verification After Merges

After merging non-trivial changes:

- run unit tests
- run integration tests
- verify planner still returns valid structured plans
- verify security policy still blocks unsafe operations
- verify executor still stores full step metadata
- verify API still returns expected status and errors

---

## Near-Term Runbook Expansion

This file should later include:

- exact startup commands
- environment setup examples
- API request examples
- dry-run verification examples
- dashboard operations
- worker/queue operations
- incident handling checklists

---

## Summary

VelocityClaw should be operated as a structured, inspectable agent system.

When in doubt:
- validate configuration first
- prefer safe execution first
- inspect the trace
- debug in pipeline order
