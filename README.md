# Velocity Claw

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
python cli.py --server
```

Run a task:

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

## API highlights

Start the server with `python cli.py --server`, then use:

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | service health |
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
  api/            FastAPI server, retry routes, dashboard helpers
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
