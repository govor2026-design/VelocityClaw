# VelocityClaw Execution Profiles Spec

This document defines the first implementation target for issue #14: **Add execution profiles: safe/dev/owner**.

---

## Goal

Introduce explicit execution profiles that control how much authority VelocityClaw has at runtime.

The first version should provide a clear and predictable way to run the same system under different trust levels.

---

## Why This Matters

Not every environment should allow the same level of agent power.

Examples:
- a demo environment should be more restrictive
- a development environment may allow broader editing and testing
- an owner-controlled environment may allow more advanced workflows

Execution profiles improve:
- safety
- predictability
- product clarity
- deployment flexibility

---

## First Version Scope

The first version should introduce three profiles:

### 1. `safe`
Default restrictive mode.

### 2. `dev`
Development-focused mode for active coding workflows.

### 3. `owner`
Expanded mode for trusted power use with stronger capabilities.

The first version should make profile differences real, not cosmetic.

---

## Core Principle

A profile must change actual runtime behavior.

It should affect things like:
- which tools are enabled
- which operations require approval
- whether writes are allowed
- whether shell/git/test workflows are available
- how broad the security policy is allowed to be

If profiles do not change behavior, the feature is not complete.

---

## Proposed Profile Definitions

### `safe`
Use when safety matters most.

Recommended characteristics:
- read-heavy behavior
- no broad write operations by default
- limited or no shell access
- limited git access
- strict network restrictions
- approval required for many sensitive steps

### `dev`
Use for active software development workflows.

Recommended characteristics:
- workspace file editing allowed
- patch engine allowed
- test runner allowed
- selected shell/git workflows allowed
- approval required for higher-risk actions only

### `owner`
Use only in highly trusted environments.

Recommended characteristics:
- broader write and repair capabilities
- broader tool access where explicitly enabled
- approval still available for especially sensitive actions
- strongest audit requirements

---

## Proposed Data Model

```json
{
  "profile": "dev",
  "capabilities": {
    "filesystem_write": true,
    "patch_engine": true,
    "test_runner": true,
    "shell": true,
    "git_write": false,
    "network": false,
    "approval_workflow": true
  }
}
```

### Core fields
- `profile`
- `capabilities`
- `approval_policy`
- `security_mode`

---

## Suggested Internal Interface

```python
class ExecutionProfileManager:
    def get_profile(self, name: str) -> dict:
        ...

    def is_tool_allowed(self, profile: str, tool: str) -> bool:
        ...

    def requires_approval(self, profile: str, step: dict) -> bool:
        ...
```

---

## Capability Matrix (Suggested First Version)

### `safe`
- filesystem read: yes
- filesystem write: limited or no
- patch engine: no or approval-only
- test runner: optional read-safe usage only
- shell: no or minimal
- git write: no
- network: no except strict allowlist
- approval workflow: yes

### `dev`
- filesystem read: yes
- filesystem write: yes within workspace
- patch engine: yes
- test runner: yes
- shell: limited safe commands
- git write: limited or approval-gated
- network: limited allowlist only
- approval workflow: yes

### `owner`
- filesystem read: yes
- filesystem write: yes
- patch engine: yes
- test runner: yes
- shell: expanded but still bounded
- git write: broader but policy-controlled
- network: allowlist-based or expanded by config
- approval workflow: optional but recommended

---

## Configuration Requirements

Profiles should be selectable via config and visible at runtime.

Recommended configuration options:
- active profile name
- per-profile capability flags
- approval policy settings
- shell/git/network limits

The first version can hardcode baseline profiles, but it should still expose the active profile clearly.

---

## API Requirements

The API should expose:
- active profile
- profile-specific behavior in status responses
- future ability to switch profiles only if explicitly allowed

At minimum, users should be able to see what profile is active.

---

## Dashboard / UI Expectations

The dashboard should later display:
- current execution profile
- what capabilities are enabled
- whether approvals are active
- whether writes/shell/git/network are restricted

This makes the trust level visible instead of hidden.

---

## Safety Rules

Profiles must not weaken core safety principles.

Important rules:
- all profiles remain workspace-scoped
- no profile bypasses path validation
- no profile bypasses traceability
- no profile silently disables auditing
- higher-power profiles must still remain explicit and bounded

`owner` should mean **broader control**, not **unbounded control**.

---

## Approval Workflow Integration

Profiles should integrate naturally with issue #13 approval workflow.

Suggested behavior:
- `safe`: broad approval coverage
- `dev`: approval only for higher-risk actions
- `owner`: approval configurable, but still available for especially sensitive steps

This creates a clear relationship between trust level and human oversight.

---

## Recommended Implementation Order

### Phase 1
- define baseline profiles
- add active profile config
- gate tool access by profile
- add tests

### Phase 2
- integrate approval workflow logic
- expose profile in API/status
- improve profile-specific capability mapping

### Phase 3
- add configurable profile customization
- add dashboard display
- add environment-specific presets

---

## Test Plan

Minimum tests:

### Capability enforcement
- safe profile blocks restricted tools
- dev profile allows expected development tools
- owner profile exposes broader capabilities as intended

### Safety consistency
- all profiles still enforce workspace boundaries
- invalid actions remain blocked regardless of profile
- profile cannot silently bypass security validation

### Integration
- API exposes active profile
- approval workflow behavior changes by profile as expected
- executor respects profile-gated tool access

---

## Success Criteria

Issue #14 is successful when VelocityClaw can:

- run under clearly defined profiles
- change real capabilities based on profile
- expose active profile clearly
- integrate profiles with security and approval behavior
- remain bounded and auditable in every mode

---

## Suggested Next Step After This Spec

Once execution profiles exist, the strongest follow-up is:

1. connect them to dashboard visibility  
2. connect them to approval workflow rules  
3. connect them to deployment/runtime defaults  

That makes profiles a real operational control layer, not just a config flag.
