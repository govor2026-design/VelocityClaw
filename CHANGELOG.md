# Changelog

All notable changes to Velocity Claw are tracked here.

## 0.2.1 - 2026-05-11

### Security

- Added protected API defaults across deployment paths.
- Added `VELOCITY_CLAW_API_KEY` to Docker and systemd deployment templates.
- Production installer now generates a random `VELOCITY_CLAW_API_KEY` on first install or when the placeholder is still present.
- Docker and systemd deployment templates now disable shell and git execution by default.
- Added tests that lock safe deployment env defaults.

### Changed

- Added support for `VELOCITY_CLAW_*` environment variables with fallback to legacy short names.
- Deployment documentation now explains API-key authentication for protected routes.
- Installer documentation now explains local API-key generation and private key handling.
- Provider SDK versions are pinned for reproducible CI and builds.

### Added

- API-key middleware for protected FastAPI routes.
- Tests for API authentication, prefixed env loading, deployment env templates, and installer hardening.
- Docker `.dockerignore` file.
- Docker healthcheck.
- MIT license file.

## 0.2.0 - 2026-04-26

### Added

- FastAPI service with health, status, diagnostics, queue, approvals, runs, retry, and dashboard endpoints.
- CLI operator commands for status, run history, retry context, release readiness, package validation, and memory cleanup.
- Persistent SQLite memory for runs, steps, artifacts, approvals, project facts, notes, and fix attempts.
- Execution profiles: safe, dev, and owner.
- Approval workflow for high-risk actions.
- Provider router observability and health state.
- Docker Compose and systemd deployment templates.
- CI workflow for package validation and tests.

### Changed

- Hardened runtime defaults for local and container deployments.
- Added API key protection for non-health API routes.
- Added provider SDK dependencies for OpenAI, Anthropic, and Google Gemini.

### Security

- Shell and Git execution are disabled by default in example configuration and container runtime.
- API requires X-API-Key or Bearer token when configured for protected routes.

## 0.1.0 - 2026-04-19

### Added

- Initial Velocity Claw AI agent foundation.
- CLI, planner, executor, Telegram entrypoint, basic memory, and safety policy scaffolding.
