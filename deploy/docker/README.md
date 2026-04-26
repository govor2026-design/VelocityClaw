# Velocity Claw Docker Compose deployment

This directory contains a Docker Compose deployment template for running Velocity Claw as an API service with safer runtime defaults.

## Files

- `docker-compose.yml` — service definition, healthcheck, volumes, and container security options.
- `velocity-claw.env.example` — production-oriented environment defaults.

## Operation notes

Use this deployment from the `deploy/docker` directory. Copy the example environment file, adjust values if needed, then start the service with Docker Compose. Use standard Docker Compose status, logs, restart, and stop commands for operations.

## Security notes

The compose template defaults to the safe execution profile, disables shell execution, drops Linux capabilities, enables `no-new-privileges`, isolates `/tmp` with tmpfs, and persists only agent data/log volumes.
