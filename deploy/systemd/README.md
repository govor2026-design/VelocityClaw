# Velocity Claw systemd deployment

This directory contains hardened Linux systemd deployment templates for running Velocity Claw as long-lived API and Telegram services.

## Files

- `velocity-claw.service` — systemd unit for the API service.
- `velocity-claw-telegram.service` — optional systemd unit for the Telegram service.
- `velocity-claw-worker.service` — optional separate persistent queue worker.
- `velocity-claw-backup.service` — oneshot online backup for both SQLite databases.
- `velocity-claw-backup.timer` — daily backup schedule with randomized delay.
- `velocity-claw.env.example` — environment template for `/etc/velocity-claw/velocity-claw.env`.
- `velocity-claw.tmpfiles.conf` — tmpfiles config for runtime directories.

## Install

```bash
sudo useradd --system --home /var/lib/velocity-claw --shell /usr/sbin/nologin velocityclaw || true
sudo mkdir -p /opt/velocityclaw /etc/velocity-claw
sudo cp deploy/systemd/velocity-claw.service /etc/systemd/system/velocity-claw.service
sudo cp deploy/systemd/velocity-claw-telegram.service /etc/systemd/system/velocity-claw-telegram.service
sudo cp deploy/systemd/velocity-claw-worker.service /etc/systemd/system/velocity-claw-worker.service
sudo cp deploy/systemd/velocity-claw-backup.service /etc/systemd/system/velocity-claw-backup.service
sudo cp deploy/systemd/velocity-claw-backup.timer /etc/systemd/system/velocity-claw-backup.timer
sudo cp deploy/systemd/velocity-claw.tmpfiles.conf /etc/tmpfiles.d/velocity-claw.conf
sudo cp deploy/systemd/velocity-claw.env.example /etc/velocity-claw/velocity-claw.env
sudo nano /etc/velocity-claw/velocity-claw.env
sudo systemd-tmpfiles --create /etc/tmpfiles.d/velocity-claw.conf
sudo systemctl daemon-reload
sudo systemctl enable velocity-claw
sudo systemctl enable --now velocity-claw-backup.timer
sudo systemctl start velocity-claw
```

Before starting the service, set `VELOCITY_CLAW_API_KEY` in `/etc/velocity-claw/velocity-claw.env` to a long random value. Protected API routes require this key through `X-API-Key` or `Authorization: Bearer <key>`.

To run Telegram alongside the API, set both `VELOCITY_CLAW_TELEGRAM_TOKEN` and `VELOCITY_CLAW_TELEGRAM_CHAT_ID`, then enable the second unit:

```bash
sudo systemctl enable --now velocity-claw-telegram
```

The Telegram unit is intentionally not enabled until its token and allowed chat are configured.

To move queue execution out of the API process, set
`VELOCITY_CLAW_QUEUE_EXECUTION_MODE=external` in the environment file and
enable the worker:

```bash
sudo systemctl enable --now velocity-claw-worker
```

Do not enable the worker while the mode is `embedded`; the CLI fails closed to
prevent the API and worker from executing the same queue.

## Operate

```bash
sudo systemctl status velocity-claw --no-pager
sudo journalctl -u velocity-claw -f
sudo systemctl restart velocity-claw
sudo systemctl status velocity-claw-telegram --no-pager
sudo journalctl -u velocity-claw-telegram -f
sudo systemctl status velocity-claw-worker --no-pager
sudo journalctl -u velocity-claw-worker -f
sudo systemctl status velocity-claw-backup.timer --no-pager
sudo systemctl start velocity-claw-backup.service
sudo journalctl -u velocity-claw-backup.service --since today
```

## Backups and restore

The daily timer creates SQLite-consistent online backups in `/var/lib/velocity-claw/backups` while API and Telegram continue running. The latest 14 backups of each database are retained. Run one manually with:

```bash
sudo -u velocityclaw /opt/velocityclaw/.venv/bin/python /opt/velocityclaw/cli.py --backup --backup-dir /var/lib/velocity-claw/backups --backup-keep 14 --json
```

Backups in the local state directory protect against application-level corruption and operator mistakes. Replicate them to separate storage if the deployment must survive loss of the host or disk.

To restore, stop both application services, preserve the current database files and their `-wal`/`-shm` sidecars, copy the selected `memory.db--*.sqlite3` and `memory.db.queue--*.sqlite3` backups to the paths configured by `VELOCITY_CLAW_MEMORY_DB_PATH`, set ownership to `velocityclaw:velocityclaw`, and start the services again. Validate each selected file first with `sqlite3 FILE 'PRAGMA integrity_check;'`.

## Security notes

The unit starts with the `safe` execution profile, disables shell and git by default, runs as a dedicated unprivileged user, and uses systemd hardening directives such as `NoNewPrivileges`, `PrivateTmp`, `ProtectSystem`, `ProtectHome`, `CapabilityBoundingSet`, and syscall architecture restrictions.

Enable shell or git only on isolated, trusted deployments where the operator accepts the risk.
