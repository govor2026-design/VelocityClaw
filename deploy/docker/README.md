# Velocity Claw Docker Compose deployment

This directory contains a Docker Compose deployment template for running Velocity Claw as API and optional Telegram services with safer runtime defaults.

## Files

- `docker-compose.yml` — service definition, healthcheck, volumes, and container security options.
- `velocity-claw.env.example` — production-oriented environment defaults.

## Operation notes

Use this deployment from the `deploy/docker` directory.

```bash
cp velocity-claw.env.example velocity-claw.env
# edit velocity-claw.env before first start
```

Set `VELOCITY_CLAW_API_KEY` to a long random value before exposing the API. Protected API routes require this key through `X-API-Key` or `Authorization: Bearer <key>`.

To run Telegram, also set `VELOCITY_CLAW_TELEGRAM_TOKEN` and `VELOCITY_CLAW_TELEGRAM_CHAT_ID`.

Then start the service:

```bash
docker compose --env-file velocity-claw.env up -d
```

Start both API and Telegram with:

```bash
docker compose --env-file velocity-claw.env --profile telegram up -d
```

The Telegram container uses an opt-in Compose profile so an empty token cannot create a restart loop in API-only deployments.

Use standard Docker Compose status, logs, restart, and stop commands for operations.

## Security notes

The compose template defaults to the safe execution profile, disables shell execution, disables git execution, drops Linux capabilities, enables `no-new-privileges`, isolates `/tmp` with tmpfs, and persists only agent data/log volumes.

Enable shell or git only on isolated, trusted deployments where the operator accepts the risk.
