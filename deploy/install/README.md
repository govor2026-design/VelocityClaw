# Velocity Claw production installer

This directory contains a production-oriented Linux installer for Velocity Claw.

## Installer

`install.sh` prepares a Linux host for running Velocity Claw with systemd.

It creates or updates:

- dedicated service user: `velocityclaw`
- dedicated service group: `velocityclaw`
- application directory: `/opt/velocityclaw`
- configuration directory: `/etc/velocity-claw`
- state directory: `/var/lib/velocity-claw`
- log directory: `/var/log/velocity-claw`
- Python virtual environment under `/opt/velocityclaw/.venv`
- systemd service and tmpfiles configuration

## Safety model

The installer uses the systemd deployment template from `deploy/systemd` and preserves the safe production defaults from `velocity-claw.env.example`.

The service starts in safe mode with the safe execution profile and shell execution disabled by default. Git execution is also disabled by default.

In short: shell/git execution disabled by default.

## API key handling

On first install, the installer copies the systemd env template to `/etc/velocity-claw/velocity-claw.env` and replaces the placeholder `VELOCITY_CLAW_API_KEY` with a random key generated locally on the target host.

If `/etc/velocity-claw/velocity-claw.env` already exists, the installer preserves it. It only replaces the API key if the value is still the placeholder.

Keep `VELOCITY_CLAW_API_KEY` private. Protected API routes require it through `X-API-Key` or `Authorization: Bearer <key>`.

## Usage notes

Run the installer from the repository root on the target Linux host:

```bash
sudo deploy/install/install.sh
```

Review `/etc/velocity-claw/velocity-claw.env` before starting the service.
