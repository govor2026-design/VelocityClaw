#!/usr/bin/env bash
set -euo pipefail

APP_USER="${APP_USER:-velocityclaw}"
APP_GROUP="${APP_GROUP:-velocityclaw}"
APP_DIR="${APP_DIR:-/opt/velocityclaw}"
CONFIG_DIR="${CONFIG_DIR:-/etc/velocity-claw}"
DATA_DIR="${DATA_DIR:-/var/lib/velocity-claw}"
LOG_DIR="${LOG_DIR:-/var/log/velocity-claw}"
SERVICE_NAME="${SERVICE_NAME:-velocity-claw}"

require_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    echo "This installer must be run as root." >&2
    exit 1
  fi
}

copy_repo() {
  local source_dir
  source_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  mkdir -p "${APP_DIR}"
  rsync -a --delete \
    --exclude='.git' \
    --exclude='.venv' \
    --exclude='__pycache__' \
    "${source_dir}/" "${APP_DIR}/"
}

ensure_user() {
  if ! id "${APP_USER}" >/dev/null 2>&1; then
    useradd --system --home "${DATA_DIR}" --shell /usr/sbin/nologin "${APP_USER}"
  fi
}

install_files() {
  mkdir -p "${CONFIG_DIR}" "${DATA_DIR}/workspace" "${LOG_DIR}"
  cp "${APP_DIR}/deploy/systemd/velocity-claw.service" "/etc/systemd/system/${SERVICE_NAME}.service"
  cp "${APP_DIR}/deploy/systemd/velocity-claw.tmpfiles.conf" "/etc/tmpfiles.d/${SERVICE_NAME}.conf"
  if [[ ! -f "${CONFIG_DIR}/velocity-claw.env" ]]; then
    cp "${APP_DIR}/deploy/systemd/velocity-claw.env.example" "${CONFIG_DIR}/velocity-claw.env"
  fi
  chown -R "${APP_USER}:${APP_GROUP}" "${DATA_DIR}" "${LOG_DIR}" "${APP_DIR}"
  chown root:"${APP_GROUP}" "${CONFIG_DIR}" "${CONFIG_DIR}/velocity-claw.env"
  chmod 0750 "${CONFIG_DIR}"
  chmod 0640 "${CONFIG_DIR}/velocity-claw.env"
}

install_python() {
  python3 -m venv "${APP_DIR}/.venv"
  "${APP_DIR}/.venv/bin/python" -m pip install --upgrade pip
  if [[ -f "${APP_DIR}/requirements.txt" ]]; then
    "${APP_DIR}/.venv/bin/pip" install -r "${APP_DIR}/requirements.txt"
  fi
}

start_service() {
  systemd-tmpfiles --create "/etc/tmpfiles.d/${SERVICE_NAME}.conf"
  systemctl daemon-reload
  systemctl enable "${SERVICE_NAME}"
  systemctl restart "${SERVICE_NAME}"
}

main() {
  require_root
  ensure_user
  copy_repo
  install_files
  install_python
  start_service
  echo "Velocity Claw installed."
  echo "Status: sudo systemctl status ${SERVICE_NAME} --no-pager"
  echo "Logs:   sudo journalctl -u ${SERVICE_NAME} -f"
}

main "$@"
