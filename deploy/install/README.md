# Velocity Claw production installer

This directory contains a production-oriented Linux installer for Velocity Claw.

## Installer

`install.sh` prepares a Linux host for running Velocity Claw with systemd.

It creates or updates:

- dedicated service user: `velocityclaw`
- application directory: `/opt/velocityclaw`
- configuration directory: `/etc/velocity-claw`
- state directory: `/var/lib/velocity-claw`
- log directory: `/var/log/velocity-claw`
- Python virtual environment under `/opt/velocityclaw/.venv`
- systemd service and tmpfiles configuration

## Safety model

The installer uses the systemd deployment template from `deploy/systemd` and preserves the safe production defaults from `velocity-claw.env.example`.

The service starts in safe mode with the safe execution profile and shell execution disabled by default.

## Usage notes

Run the installer from the repository root on the target Linux host. Review `/etc/velocity-claw/velocity-claw.env` before starting the service.
