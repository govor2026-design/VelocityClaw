# Velocity Claw deployment guide

This guide consolidates the supported deployment paths for Velocity Claw.

## Deployment paths

| Path | Best for | Files |
| --- | --- | --- |
| Production installer | Linux host with systemd | `deploy/install/install.sh`, `deploy/install/README.md` |
| Manual systemd | Controlled server setup | `deploy/systemd/*` |
| Docker Compose | Container-based deployment | `deploy/docker/*` |

## Recommended production path

Use the production installer when deploying to a Linux server that should run Velocity Claw as a persistent systemd service.

The installer prepares:

- dedicated service user: `velocityclaw`
- app directory: `/opt/velocityclaw`
- config directory: `/etc/velocity-claw`
- state directory: `/var/lib/velocity-claw`
- log directory: `/var/log/velocity-claw`
- Python virtual environment
- systemd unit
- tmpfiles runtime directories

After installation, review `/etc/velocity-claw/velocity-claw.env` before starting the service.

## API authentication

All API routes except `/health` are protected. Set a long random value before exposing the service:

```bash
VELOCITY_CLAW_API_KEY=change-this-long-random-key
```

Clients can authenticate with either header:

```text
X-API-Key: <key>
Authorization: Bearer <key>
```

If no API key is configured, protected routes fail closed instead of running open.

Full endpoint reference:

- `docs/API.md`

## Manual systemd deployment

Use manual systemd deployment when you want to copy and adjust unit files yourself.

Relevant files:

- `deploy/systemd/velocity-claw.service`
- `deploy/systemd/velocity-claw.env.example`
- `deploy/systemd/velocity-claw.tmpfiles.conf`
- `deploy/systemd/README.md`

The systemd unit runs the API service with hardened defaults such as:

- dedicated unprivileged user
- `NoNewPrivileges=true`
- `PrivateTmp=true`
- `ProtectSystem=full`
- `ProtectHome=true`
- empty capability bounding set
- native syscall architecture restriction

## Docker Compose deployment

Use Docker Compose when you want a containerized deployment with persistent volumes.

Relevant files:

- `deploy/docker/docker-compose.yml`
- `deploy/docker/velocity-claw.env.example`
- `deploy/docker/README.md`

The Compose template includes:

- API healthcheck
- persistent data volume
- persistent log volume
- dropped Linux capabilities
- `no-new-privileges`
- tmpfs for `/tmp`

## Safe production defaults

All deployment paths default to conservative runtime settings:

- production environment
- safe mode enabled
- trusted mode disabled
- execution profile: `safe`
- shell execution disabled
- git execution disabled
- memory enabled
- state stored under `/var/lib/velocity-claw`

Enable shell or git only on isolated, trusted deployments where the operator accepts the risk.

## Operational checks

For a healthy deployment, verify:

- the API service starts successfully
- `/health` responds through the configured API port
- protected API routes require `X-API-Key` or Bearer authentication
- `/dashboard/v2` loads with authentication
- `/runs` returns recent runs with authentication
- `/approvals` returns pending approvals with authentication
- `docs/API.md` matches the deployed API surface
- logs are being written or available through the process manager
- the memory database path is writable by the service user
- the workspace directory exists and is writable by the service user
- the configured execution profile is intentional

## Related operator tools

The CLI includes local admin commands for common operations:

- status output
- release readiness
- recent runs
- last failed run
- retry context
- retry run
- JSON output mode

See `cli.py` for exact flags.
