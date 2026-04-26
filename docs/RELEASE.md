# Velocity Claw release guide

This guide defines the minimal release checklist for Velocity Claw.

## Version metadata

The release version is tracked in two places:

- `VERSION`
- `velocity_claw/__version__.py`

Both values must match before a release.

## Release checklist

Before cutting a release, verify:

- CI is green on `master`
- `VERSION` matches `velocity_claw.__version__.__version__`
- release readiness reports no blocking issues
- deployment documentation is up to date
- systemd templates are present
- Docker Compose templates are present
- production installer is present
- CLI admin commands are available
- retry/replay routes and retry context are covered by tests

## Release readiness command

Use the operator CLI release readiness command to inspect current project readiness.

The readiness result should be reviewed before tagging or publishing any package.

## Version bump rules

Use semantic versioning:

- patch version for bug fixes and small internal hardening
- minor version for new operator features, deployment layers, API routes, or workflow additions
- major version for breaking API or runtime behavior changes

## Blocking conditions

Do not release if any of these are true:

- tests are failing
- deployment docs are inconsistent with deployment files
- safe production defaults are missing
- release readiness has blocking issues
- version metadata is inconsistent
- a recently merged security or execution-policy change lacks tests
