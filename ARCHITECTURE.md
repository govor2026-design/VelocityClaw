# VelocityClaw Architecture

This document describes the current architecture of VelocityClaw and the intended direction for its evolution.

---

## Overview

VelocityClaw is a self-hosted agent framework for structured task execution with a focus on:

- safe tool execution
- workspace isolation
- structured planning
- execution traceability
- model-provider routing
- extensibility through tools, API, and future UI layers

At a high level, the system follows this pipeline:

**task -> planner -> security validation -> executor -> memory -> summary**

---

## Core Components

### 1. Planner
The planner converts a user task into a structured plan.

Responsibilities:
- build a planning prompt
- request a plan from the model router
- validate the returned JSON plan
- return structured steps with:
  - id
  - title
  - tool
  - args
  - expected_output

Key property:
- planning must remain deterministic and schema-driven

---

### 2. Model Router
The model router handles provider selection and normalized responses.

Responsibilities:
- select provider candidates based on task type
- handle provider fallback
- normalize response shape across providers
- distinguish:
  - configuration errors
  - request errors
  - response errors

Key property:
- planner and executor should never depend on provider-specific response formats

---

### 3. Security Layer
The security layer controls what the agent is allowed to do.

Responsibilities:
- validate workspace file paths
- validate URLs against allowlist rules
- validate shell commands
- validate git commands
- enforce execution profiles and access boundaries

Key property:
- all dangerous actions should fail early and explicitly

---

### 4. Executor
The executor runs structured plan steps.

Responsibilities:
- dispatch step execution based on `tool` and `args`
- return structured step result objects
- keep execution deterministic
- surface status/result/error clearly

Key property:
- executor should never infer tools from natural language if tool metadata already exists

---

### 5. Tool Layer
The tool layer provides concrete system capabilities.

Current tool areas include:
- filesystem
- shell
- git
- HTTP
- JSON/text manipulation

Design expectations:
- all tools must respect workspace and policy rules
- tool outputs should be structured whenever possible
- tools should be individually testable

---

### 6. Memory Store
The memory layer stores execution traces and persistent data.

Responsibilities:
- create and track `run_id`
- store per-step results
- store artifacts
- preserve preferences and future project memory

Key property:
- the system should be inspectable after every run

---

### 7. API Layer
The API provides an integration surface for clients.

Responsibilities:
- accept structured task requests
- return run identifiers and step traces
- surface failures with clear status codes
- provide an eventual foundation for dashboard and worker integration

Key property:
- API responses should reflect internal structured state, not raw internal exceptions

---

## Execution Flow

1. A task enters through CLI, API, or future UI.
2. Planner generates a structured plan.
3. Security validation checks each step.
4. Executor runs steps using allowed tools.
5. Memory stores run and step results.
6. Final summary is returned.

This separation is important because it keeps planning, validation, execution, and persistence from collapsing into one hard-to-debug layer.

---

## Current Strengths

- structured planning model
- workspace-aware security model
- provider fallback support
- persistent run/step memory
- API and CLI foundation
- initial test coverage

---

## Current Growth Areas

The current roadmap pushes architecture toward:

- patch-based code editing
- test execution and failure parsing
- symbol-aware code navigation
- dry-run mode
- artifact and diff workflows
- dashboard and approval workflows
- background workers and concurrency control

---

## Architectural Principles

VelocityClaw should continue following these rules:

1. **Structure over heuristics**  
Prefer schema-driven execution over guessing.

2. **Security by default**  
Unsafe operations should be blocked unless explicitly allowed.

3. **Traceability first**  
Every run and step should remain inspectable.

4. **Composable tools**  
Capabilities should live in isolated, testable tools.

5. **Progressive productization**  
CLI/API first, dashboard and worker orchestration second.

---

## Near-Term Target Architecture

Near-term evolution should move toward this flow:

**task -> planner -> security -> symbol navigation -> patch edit -> diff -> test run -> failure parse -> memory/artifacts -> summary**

That path gives VelocityClaw the strongest practical improvement as a development agent.


## Current Maturity

VelocityClaw is currently best described as an **advanced MVP / strong foundation+**.
It now includes code-editing, test-running, symbol navigation, auto-fix, profile gating, approval foundations, dashboard foundations, queue foundations, and artifacts, but still has room to grow into a fuller product/runtime system.
