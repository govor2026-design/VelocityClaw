# Release automation

Velocity Claw publishes releases through `.github/workflows/release.yml`.

## Automatic trigger

The workflow starts after a push to `master` that changes `VERSION` or the release workflow itself. This allows a version-bump pull request to publish its release after merge and also lets workflow repairs publish a pending version.

## Validation gates

Before publication the workflow:

- validates `VERSION`, `velocity_claw/__version__.py`, and `pyproject.toml`;
- runs the complete test suite;
- audits pinned dependencies;
- verifies that the tag equals `v<VERSION>`;
- builds the wheel and source distribution;
- generates notes from the matching section in `CHANGELOG.md`.

A failed gate stops publication.

## GitHub Release behavior

For a new version, the workflow creates the tag and GitHub Release at the validated `master` commit. It attaches the wheel, source archive, and validation summary.

For an existing version, the workflow updates the release notes and replaces package assets. This makes manual reruns safe after an interrupted publication.

## Manual run

The workflow can be started manually. The optional tag must match `v<VERSION>`. When omitted, the workflow derives the tag from `VERSION`.

## Permissions

The workflow uses the repository GitHub token with `contents: write` only for tag and release publication. Source checkout, tests, package validation, and dependency audit run before that publication step.
