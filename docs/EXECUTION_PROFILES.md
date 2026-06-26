# Execution profiles v2

Velocity Claw uses two independent security layers:

1. the selected execution profile decides whether a tool is allowed, approval-gated, or denied;
2. runtime settings and security validation decide whether the allowed action can execute now.

Approval never overrides a hard profile deny or a disabled runtime capability.

## Policy modes

- `allow` — the profile grants the tool and no profile approval is required;
- `approval` — the profile grants the tool only after an approval decision;
- `deny` — the profile does not grant the tool; approval cannot elevate it.

Unknown tools default to `deny` for every profile.

## Tool matrix

| Tool group | safe | dev | owner |
| --- | --- | --- | --- |
| analysis, filesystem read, code navigation | allow | allow | allow |
| git inspection | allow | allow | allow |
| patch preview | allow | allow | allow |
| test runner | allow | allow | allow |
| filesystem write | deny | allow | allow |
| patch apply | deny | allow | allow |
| shell | deny | approval | allow |
| git write | deny | deny | allow |
| HTTP GET/POST | deny | deny | allow |

## Runtime constraints

Profile access is necessary but not sufficient:

- `shell.run` is blocked when `SHELL_ENABLED=false`;
- `git.inspect` and `git.run` are blocked when `GIT_ENABLED=false`;
- HTTP tools remain restricted by `ALLOWED_HOSTS` and URL validation;
- workspace path restrictions and command allowlists remain active;
- dry-run changes execution output but does not bypass policy or validation.

The API distinguishes:

- `allowed`: the profile grants the capability;
- `allowed_now`: the tool can execute with current approval and runtime state;
- `blocked`: profile or runtime policy prevents execution;
- `policy_mode`: `allow`, `approval`, or `deny`.

## Approval behavior

`dev.shell.run` pauses before execution. After approval, the same step still passes:

- the stored run profile;
- runtime capability checks;
- command/path/URL/git security validation;
- normal executor validation.

The next approval-gated step creates a new approval boundary. One approval does not approve the rest of the plan.

Steps with `args.require_approval=true` remain approval-gated in any profile that otherwise grants the tool.

A denied tool returns a failed step with a policy explanation. It does not create a misleading approval request.

## Run profile stability

Each run stores its execution profile. Approval continuation uses that stored profile, not the current process setting. Changing the server from `dev` to `owner` after an approval request therefore cannot silently elevate the paused run.

## Operator endpoints

| Endpoint | Purpose |
| --- | --- |
| `GET /profiles` | All profiles, capabilities, and tool modes |
| `GET /profiles/active` | Active profile, effective tool policy, and runtime constraints |
| `GET /profiles/explain/{tool}` | Explanation for one tool; replace dots with `__` |
| `POST /approvals/explain` | Approval or deny explanation for a proposed step |

Examples:

```text
GET /profiles/explain/shell__run
GET /profiles/explain/git__run
```
