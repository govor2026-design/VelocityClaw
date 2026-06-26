# Diff preview for file modifications

Velocity Claw generates a unified diff for every direct text-file modification before the updated content is written.

Supported actions:

- `fs.write`
- `fs.append`
- `fs.replace`
- `patch.preview`
- `patch.apply`

Direct filesystem actions return a structured result containing:

- action name;
- workspace-relative path;
- whether content changed;
- unified diff;
- byte counts before and after the modification.

A no-op write returns `changed: false` and an empty diff.

When a step result contains a non-empty `diff`, the agent stores it as a run artifact with:

- artifact type `diff`;
- the current `run_id`;
- the producing `step_id`;
- the name `step_<step_id>_diff`.

Diff artifacts are available through:

- `GET /runs/{run_id}/detail/v2`;
- `GET /runs/{run_id}/artifacts/v2`;
- Dashboard v2 run and step inspector links;
- the classic run view and forensics surfaces.

All paths remain constrained to the configured workspace, binary files are rejected, and the configured maximum file size is enforced before writing.
