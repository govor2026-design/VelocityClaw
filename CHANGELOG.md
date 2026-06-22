# Changelog

All notable changes to Velocity Claw are tracked here.

## 0.2.3 - 2026-06-22

### Added

- Added protected `/version` API endpoint with product, package version, release stage, environment, and runtime-mode metadata.
- Added deployed version and release-stage surfaces to Dashboard v2 and Diagnostics v2.
- Added Approval v2 operator index with risk-priority sorting, filters, normalized decision context, artifact/history counts, and related operator links.
- Added Approval continuation flow v3 with explicit resume boundaries, continuation history, source-step deduplication, and guarded replay behavior.
- Added Queue persistence v2 with SQLite schema migration, startup recovery, queued-job rescheduling, duplicate scheduling protection, retry limits, and recovery metadata.
- Added Queue v2 runtime, recover, requeue, and cancel operator endpoints.
- Added Queue v2 operator documentation and deployment smoke coverage.
- Added CI failure artifacts containing pytest output for easier workflow diagnostics.

### Changed

- Approval v2 decisions now resume approved runs from a precise continuation boundary instead of replaying the approved source step.
- Dashboard v2, Diagnostics v2, README, deployment documentation, and the API guide now expose the deployed package version flow.
- Diagnostics v2 now includes queue persistence status, active and scheduled worker counts, retry limits, startup recovery details, and queue recovery risk flags.
- Production queue settings now apply `QUEUE_MAX_ATTEMPTS` and `QUEUE_RECOVER_ON_STARTUP` before startup scheduling.
- Forced queue retries now start a new retry cycle while preserving the previous attempt count in lifecycle history.

### Fixed

- Fixed persisted `running` jobs remaining falsely active after an unclean restart.
- Fixed legacy requeue behavior that changed status without scheduling a worker.
- Fixed cancelled running jobs being overwritten as completed when the runner returned later.
- Fixed duplicate scheduling during repeated recovery requests.
- Fixed exhausted `force=true` retries being immediately blocked again by the attempt cap.
- Fixed startup event registration compatibility with the pinned FastAPI version.
- Stabilized background-worker API tests by waiting for terminal state inside the application lifespan.

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
