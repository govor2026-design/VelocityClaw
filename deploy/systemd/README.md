# Velocity Claw systemd deployment

This directory contains hardened Linux systemd deployment templates for running Velocity Claw as long-lived API and Telegram services.

## Files

- `velocity-claw.service` — systemd unit for the API service.
- `velocity-claw-telegram.service` — optional systemd unit for the Telegram service.
- `velocity-claw.env.example` — environment template for `/etc/velocity-claw/velocity-claw.env`.
- `velocity-claw.tmpfiles.conf` — tmpfiles config for runtime directories.

## Install

```bash
sudo useradd --system --home /var/lib/velocity-claw --shell /usr/sbin/nologin velocityclaw || true
sudo mkdir -p /opt/velocityclaw /etc/velocity-claw
sudo cp deploy/systemd/velocity-claw.service /etc/systemd/system/velocity-claw.service
sudo cp deploy/systemd/velocity-claw-telegram.service /etc/systemd/system/velocity-claw-telegram.service
sudo cp deploy/systemd/velocity-claw.tmpfiles.conf /etc/tmpfiles.d/velocity-claw.conf
sudo cp deploy/systemd/velocity-claw.env.example /etc/velocity-claw/velocity-claw.env
sudo nano /etc/velocity-claw/velocity-claw.env
sudo systemd-tmpfiles --create /etc/tmpfiles.d/velocity-claw.conf
sudo systemctl daemon-reload
sudo systemctl enable velocity-claw
sudo systemctl start velocity-claw
```

Before starting the service, set `VELOCITY_CLAW_API_KEY` in `/etc/velocity-claw/velocity-claw.env` to a long random value. Protected API routes require this key through `X-API-Key` or `Authorization: Bearer <key>`.

To run Telegram alongside the API, set both `VELOCITY_CLAW_TELEGRAM_TOKEN` and `VELOCITY_CLAW_TELEGRAM_CHAT_ID`, then enable the second unit:

```bash
sudo systemctl enable --now velocity-claw-telegram
```

The Telegram unit is intentionally not enabled until its token and allowed chat are configured.

## Operate

```bash
sudo systemctl status velocity-claw --no-pager
sudo journalctl -u velocity-claw -f
sudo systemctl restart velocity-claw
sudo systemctl status velocity-claw-telegram --no-pager
sudo journalctl -u velocity-claw-telegram -f
```

## Security notes

The unit starts with the `safe` execution profile, disables shell and git by default, runs as a dedicated unprivileged user, and uses systemd hardening directives such as `NoNewPrivileges`, `PrivateTmp`, `ProtectSystem`, `ProtectHome`, `CapabilityBoundingSet`, and syscall architecture restrictions.

Enable shell or git only on isolated, trusted deployments where the operator accepts the risk.
