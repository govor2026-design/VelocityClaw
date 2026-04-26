#!/usr/bin/env bash
set -euo pipefail

APP_USER="${APP_USER:-velocityclaw}"
APP_GROUP="${APP_GROUP:-velocityclaw}"
APP_DIR="${APP_DIR:-/opt/velocityclaw}"
CONFIG_DIR="${CONFIG_DIR:-/etc/velocity-claw}"
STATE_DIR="${STATE_DIR:-/var/lib/velocity-claw}"
LOG_DIR="${LOG_DIR:-/var/log/velocity-claw}"
SERVICE_NAME="${SERVICE_NAME:-velocity-claw}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

require_root() {
  if [ "$(id -u)" -ne 0 ]; then
    echo "This installer must run as root." >&2
    exit 1
  fi
}

require_file() {
  if [ ! -f "$1" ]; then
    echo "Missing required file: $1" >&2
    exit 1
  fi
}

create_user() {
  if ! id "$APP_USER" >/dev/null 2>&1; then
    useradd --system --home "$STATE_DIR" --shell /usr/sbin/nologin "$APP_USER"
  fi
}

create_directories() {
  mkdir -p "$APP_DIR" "$CONFIG_DIR" "$STATE_DIR/workspace" "$LOG_DIR"
  chown -R "$APP_USER:$APP_GROUP" "$STATE_DIR" "$LOG_DIR"
  chmod 0750 "$CONFIG_DIR" "$STATE_DIR" "$STATE_DIR/workspace" "$LOG_DIR"
}

install_project_files() {
  rsync -a --delete --exclude .git --exclude .venv ./ "$APP_DIR/"
  chown -R "$APP_USER:$APP_GROUP" "$APP_DIR"
}

install_python_env() {
  cd "$APP_DIR"
  sudo -u "$APP_USER" "$PYTHON_BIN" -m venv .venv
  sudo -u "$APP_USER" .venv/bin/python -m pip install --upgrade pip
  if [ -f requirements.txt ]; then
    sudo -u "$APP_USER" .venv/bin/python -m pip install -r requirements.txt
  fi
}

install_config() {
  require_file "$APP_DIR/deploy/systemd/velocity-claw.env.example"
  if [ ! -f "$CONFIG_DIR/velocity-claw.env" ]; then
    cp "$APP_DIR/deploy/systemd/velocity-claw.env.example" "$CONFIG_DIR/velocity-claw.env"
  fi
  chown root:"$APP_GROUP" "$CONFIG_DIR/velocity-claw.env"
  chmod 0640 "$CONFIG_DIR/velocity-claw.env"
}

install_systemd() {
  require_file "$APP_DIR/deploy/systemd/velocity-claw.service"
  require_file "$APP_DIR/deploy/systemd/velocity-claw.tmpfiles.conf"
  cp "$APP_DIR/deploy/systemd/velocity-claw.service" "/etc/systemd/system/$SERVICE_NAME.service"
  cp "$APP_DIR/deploy/systemd/velocity-claw.tmpfiles.conf" "/etc/tmpfiles.d/$SERVICE_NAME.conf"
  systemd-tmpfiles --create "/etc/tmpfiles.d/$SERVICE_NAME.conf"
  systemctl daemon-reload
  systemctl enable "$SERVICE_NAME"
}

print_summary() {
  cat <<EOF
Velocity Claw installation finished.

Service: $SERVICE_NAME
App dir: $APP_DIR
Config: $CONFIG_DIR/velocity-claw.env
State: $STATE_DIR
Logs: $LOG_DIR

Next steps:
1. Review $CONFIG_DIR/velocity-claw.env
2. Start the service with: systemctl start $SERVICE_NAME
3. Check status with: systemctl status $SERVICE_NAME --no-pager
EOF
}

main() {
  require_root
  create_user
  create_directories
  install_project_files
  install_python_env
  install_config
  install_systemd
  print_summary
}

main "$@"
