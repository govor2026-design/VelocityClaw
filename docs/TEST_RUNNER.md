# Test runner

Velocity Claw exposes test execution through the `test.run` tool.

## Supported runners

- `pytest`
- `python -m pytest`
- `npm test`

Commands are always executed with `shell=False`. The runner name is selected from the fixed list above; arbitrary executable strings are rejected.

## Workspace restrictions

- the process working directory defaults to `WORKSPACE_ROOT`;
- an optional `cwd` must resolve to an existing directory inside the workspace;
- pytest targets and node IDs are validated against workspace boundaries;
- npm/Jest test targets must also resolve inside the workspace;
- subprocesses cannot request a timeout greater than `COMMAND_TIMEOUT`.

## Targeted pytest execution

`test.run` accepts:

- `target`
- `nodeid`
- `keyword`
- `marker`
- `extra_args`

Only a small allowlist of extra pytest arguments is forwarded. Examples include `-q`, `-x`, `--lf`, `--maxfail=1`, and short traceback modes.

## npm and Jest execution

`npm test` may receive a workspace test target and allowlisted arguments after `--`.

Allowlisted examples include:

- `--runInBand`
- `--watch=false`
- `--passWithNoTests`
- `--coverage`
- `--testNamePattern=...`
- `--testPathPattern=...`
- `--maxWorkers=...`

Unknown npm arguments are discarded instead of being forwarded.

## Structured result

Every test result contains:

- runner and command array;
- target and selectors;
- resolved working directory;
- effective timeout;
- exit code and normalized status;
- stdout and stderr;
- duration;
- passed/failed/error/skipped summary;
- parsed failure objects.

Normalized statuses are:

- `passed`
- `failed`
- `timeout`
- `runner_unavailable`
- `simulated`

A `failed`, `timeout`, or `runner_unavailable` test result marks the enclosing agent step as failed. The plan therefore stops instead of continuing after an unsuccessful verification step.

## Failure objects

Pytest and common Jest output are normalized into objects containing:

- failed test name;
- node ID or test title;
- file;
- line when available;
- assertion/message;
- traceback summary;
- failure kind.

The full stdout/stderr and parsed failure list remain in the step result. Velocity Claw persists test logs and parsed failures as run artifacts for retry, failed-run resume, reporting, and auto-fix diagnostics.

## Dry run

In dry-run mode no subprocess is started. The result returns the exact command array, working directory, effective timeout, and `status=simulated` while keeping path and argument validation active.
