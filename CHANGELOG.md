# Changelog

All notable changes to Velocity Claw are tracked here.

## 0.2.2 - 2026-05-16

### Added

- Added Dashboard v2 operator surface.
- Added Approval workflow v2 detail and guarded decision endpoints.
- Added Execution profiles v2 tool-access explanations.
- Added Run detail v2 and Artifact index v2 endpoints.
- Added Diagnostics v2 endpoint with runtime summary, risk flags, queue state, approval state, provider state, release readiness, metrics, and troubleshooting links.
- Added `/version` endpoint for deployed service version and runtime-mode verification.
- Added API guide for current v2 endpoints.
- Added deployed API smoke-check script.

### Changed

- Dashboard v2 now links to Run detail v2, Artifact index v2, Approval v2, forensics, reports, classic run views, Diagnostics v2, and `/version`.
- Dashboard v2 now surfaces package version, release stage, compact risk flags, and a Diagnostics section.
- API smoke checks now include Diagnostics v2 and `/version`.
- API smoke auth check now expects `401` for protected routes without an API key when the server is configured with an API key.
- README and deployment docs now point operators to the API guide and version verification flow.

### Fixed

- Fixed API smoke-test expectation for configured authenticated deployments.
- Added tests to lock smoke-check endpoints and auth-status expectations.

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
