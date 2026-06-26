# Dry-run execution mode

Velocity Claw dry-run mode validates a plan without applying mutating actions.

## Enablement

Set:

```text
VELOCITY_CLAW_DRY_RUN=true
```

or pass `dry_run=true` in a tool step.

The global setting is authoritative. When `DRY_RUN=true`, a step cannot disable it with `dry_run=false`.

## Simulated actions

The following actions are validated but not applied:

- `fs.write`
- `fs.append`
- `fs.replace`
- `patch.apply`
- `test.run`
- `shell.run`
- `git.run`
- `http.post`

Read-only operations such as filesystem reads, code navigation, analysis, patch preview, git inspection, and HTTP GET may still run when their profile and runtime policies allow them.

## Validation remains active

Dry-run is not a policy bypass. Before returning `status=simulated`, Velocity Claw still applies:

- execution-profile allow/approval/deny rules;
- `SHELL_ENABLED` and `GIT_ENABLED` runtime gates;
- workspace path validation;
- file-size validation;
- replacement-target validation;
- patch safety and ambiguity checks;
- shell and git command allowlists;
- working-directory validation;
- URL and host allowlist validation;
- test runner, argument, timeout, and workspace validation.

A denied or invalid action returns a failed step instead of a simulated success.

## Simulation result

Simulated actions return structured metadata including:

- `status: simulated`
- `dry_run: true`
- `validated: true`
- action/tool name
- path, command, URL, or test command as applicable
- expected size or diff information when available

The enclosing agent step remains successful and is marked `simulated=true`. This lets later inspection steps continue while preserving the distinction between actual and simulated execution.

## Reports and forensics

Stored run reports include `dry_run_overview` with:

- whether the run contains simulations;
- number of simulated actions;
- simulated step IDs, tools, paths, and commands;
- validation state and attempt metadata.

Run forensics include the same actions under `dry_run`. The executive summary explicitly states how many actions were simulated and that the listed mutations were not applied.

## Safety examples

A dry-run filesystem write outside `WORKSPACE_ROOT` is rejected.

A dry-run replacement whose old text is absent is rejected.

A dry-run shell or git command remains blocked when its runtime capability is disabled.

A dry-run HTTP POST validates the destination but sends no request.

A dry-run patch returns its unified diff while leaving the file unchanged.
