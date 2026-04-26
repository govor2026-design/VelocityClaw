# Velocity Claw systemd deployment

This directory contains a hardened Linux systemd deployment template for running Velocity Claw as a long-lived API service.

## Files

- `velocity-claw.service` — systemd unit for the API service.
- `velocity-claw.env.example` — environment template for `/etc/velocity-claw/velocity-claw.env`.
- `velocity-claw.tmpfiles.conf` — tmpfiles config for runtime directories.

## Install

```bash
sudo useradd --system --home /var/lib/velocity-claw --shell /usr/sbin/nologin velocityclaw || true
sudo mkdir -p /opt/velocityclaw /etc/velocity-claw
sudo cp deploy/systemd/velocity-claw.service /etc/systemd/system/velocity-claw.service
sudo cp deploy/systemd/velocity-claw.tmpfiles.conf /etc/tmpfiles.d/velocity-claw.conf
sudo cp deploy/systemd/velocity-claw.env.example /etc/velocity-claw/velocity-claw.env
sudo systemd-tmpfiles --create /etc/tmpfiles.d/velocity-claw.conf
sudo systemctl daemon-reload
sudo systemctl enable velocity-claw
sudo systemctl start velocity-claw
```

## Operate

```bash
sudo systemctl status velocity-claw --no-pager
sudo journalctl -u velocity-claw -f
sudo systemctl restart velocity-claw
```

## Security notes

The unit starts with the `safe` execution profile, disables shell by default, runs as a dedicated unprivileged user, and uses systemd hardening directives such as `NoNewPrivileges`, `PrivateTmp`, `ProtectSystem`, `ProtectHome`, `CapabilityBoundingSet`, and syscall architecture restrictions.
