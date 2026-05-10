# Velocity Claw

![CI](https://github.com/govor2026-design/VelocityClaw/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

<div align="center">
  <img src="assets/velocity_claw_falcon.png" alt="Velocity Claw - Falcon" width="400"/>
</div>

Velocity Claw is a self-hosted AI dev-agent for controlled code work, repo inspection, patch editing, test execution, run tracing, approvals, retry/replay workflows, and operator-driven deployment.

Current state: **advanced MVP / strong foundation+**. The project already has a working agent core, API, CLI, Telegram entrypoint, memory, approval gates, retry/replay, release readiness, and deployment templates. It is not yet a fully polished multi-user SaaS product, but the operational foundation is now solid.

---

## What Velocity Claw does

Velocity Claw is built around a safe execution loop:

1. plan the task
2. validate the tool/action against policy
3. execute bounded steps
4. store run/step/artifact trace
5. expose reports, forensics, approvals, and retry context
6. let the operator review or continue

It is designed for self-hosted development automation where auditability and owner control matter more than blind autonomy.

---

## Core capabilities

### Agent core

- planner-driven task orchestration
- execution profiles: `safe`, `dev`, `owner`
- security policy for paths, commands, URLs, and git operations
- approval workflow with operator hints
- persistent memory for runs, steps, artifacts, project facts, approvals, and fix attempts
- retry/replay context from previous run reports and forensics

### Code and repository tools

- patch engine with diff preview and code-edit safety checks
- symbol-aware navigation for functions/classes/imports
- pytest runner with structured output and parsed failures
- restricted git inspection and execution
- safe filesystem, shell, HTTP, Docker, and editor utility tools

### Operations layer

- FastAPI server
- HTML dashboard foundation
- operations console snapshot
- queue foundation
- metrics and diagnostics
- provider/router observability
- release readiness evaluator
- operator CLI admin commands
- Telegram bot entrypoint

### Deployment and release

- hardened systemd service template
- Docker Compose template
- production Linux install script
- unified deployment guide
- version metadata
- release checklist

---

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python cli.py --status
```

Run the API:

```bash
API_KEY="change-this-long-random-key" python cli.py --server
```

Call a protected API endpoint:

```bash
curl -H "X-API-Key: change-this-long-random-key" http://127.0.0.1:8000/status
```

Run a task from CLI:

```bash
python cli.py --task "Analyze the repository structure"
```

Run tests:

```bash
pytest -q
```

---

## Operator CLI

The CLI supports local admin workflows:

```bash
python cli.py --status --json
python cli.py --release-readiness --json
python cli.py --runs --runs-limit 10 --json
python cli.py --last-failed --json
python cli.py --retry-context <RUN_ID> --json
python cli.py --retry-run <RUN_ID> --json
```

Use JSON mode for scripts and operator tooling.

---

## API security

All API routes except `GET /health` are protected by API-key middleware.

Supported authentication headers:

```text
X-API-Key: <your-api-key>
Authorization: Bearer <your-api-key>
```

Configure one of these environment variables before exposing the service:

```bash
API_KEY="change-this-long-random-key"
# or
VELOCITY_CLAW_API_KEY="change-this-long-random-key"
```

If no API key is configured, protected routes return `503 api_key_not_configured` instead of running open.

---

## API highlights

Start the server with `python cli.py --server`, then use:

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | public service health |
| `GET /metrics` | runtime metrics |
| `GET /diagnostics` | diagnostics snapshot |
| `GET /ops/console` | operations console data |
| `GET /dashboard` | dashboard HTML |
| `POST /task` | run a task |
| `POST /modes/run` | run a high-level mode |
| `POST /queue/submit` | enqueue a task |
| `GET /runs` | list recent runs |
| `GET /runs/{run_id}` | inspect a run |
| `GET /runs/{run_id}/forensics` | inspect run forensics |
| `GET /runs/{run_id}/report` | inspect run report |
| `GET /runs/{run_id}/retry-context` | inspect retry context |
| `POST /runs/{run_id}/retry` | retry a previous run |
| `GET /approvals` | list pending approvals |
| `POST /approvals/explain` | explain approval requirement |
| `GET /release/readiness` | release readiness |
| `GET /providers/observability` | provider/router observability |
| `GET /git/summary` | safe repo summary |

Read-side API endpoints use stable `status: ok` envelopes.

---

## Security modes

| Mode | Intended use | Default posture |
| --- | --- | --- |
| `safe` | Production/default operator mode | Read-oriented, approval-heavy, shell/git disabled unless explicitly enabled |
| `dev` | Local development and debugging | More permissive workspace operations, still policy checked |
| `owner` | Trusted single-owner automation | Highest capability profile; never use in production without `ALLOWED_USERS` |

Important defaults:

- `SAFE_MODE=true`
- `TRUSTED_MODE=false`
- `EXECUTION_PROFILE=safe`
- `SHELL_ENABLED=false`
- `GIT_ENABLED=false`

Enable shell or git only when the deployment is trusted and isolated.

---

## Deployment

Supported deployment paths:

| Path | Best for | Files |
| --- | --- | --- |
| Production installer | Linux host with systemd | `deploy/install/*` |
| Manual systemd | Controlled server setup | `deploy/systemd/*` |
| Docker Compose | Container deployment | `deploy/docker/*` |

Main guide:

- `docs/DEPLOYMENT.md`

Release guide:

- `docs/RELEASE.md`

Production defaults are conservative:

- safe mode enabled
- trusted mode disabled
- execution profile: `safe`
- shell execution disabled
- git execution disabled
- state under `/var/lib/velocity-claw`

---

## Version

Current version:

- `VERSION`
- `velocity_claw/__version__.py`

Both files are tested for consistency.

---

## Project structure

```text
velocity_claw/
  api/            FastAPI server, auth, retry routes, dashboard helpers
  config/         settings and env loading
  core/           agent, queue, modes, metrics, auto_fix, release
  executor/       tool dispatch
  logs/           logger
  memory/         SQLite run/step/artifact/project facts store
  models/         provider routing
  planner/        plan generation
  prompts/        system prompts
  security/       policy, profiles, approval workflow
  telegram_bot/   Telegram interface
  tools/          fs, shell, git, http, patch, code_nav, test_runner, docker, editor

deploy/
  docker/         Docker Compose deployment
  install/        production Linux installer
  systemd/        hardened systemd deployment

docs/
  DEPLOYMENT.md   unified deployment guide
  RELEASE.md      release checklist and versioning guide
```

---

## What is still not final

Velocity Claw is strong, but not finished as a full commercial SaaS product.

Known next maturity areas:

- richer dashboard frontend
- deeper approval resume UX
- stronger persistent worker infrastructure
- multi-project and multi-user model
- packaging automation and tagged releases
- richer artifact explorer
- production observability stack

---

## Positioning

Velocity Claw is currently best described as:

**advanced self-hosted AI dev-agent MVP with strong operational foundation.**

It is suitable for continued development, controlled server-side experimentation, repo automation workflows, and building toward a production-grade autonomous coding operator.
