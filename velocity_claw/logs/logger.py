"""
Centralized logging layer for VelocityClaw.

The helper is intentionally stdlib-only and safe to import from CLI, API,
Telegram bot, runtime boundaries, tests, and deployment scripts.
"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

_STATE = {"configured": False}

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d %(message)s"
_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"
DEFAULT_LOG_DIR = "logs"
DEFAULT_LOG_FILE = "velocity_claw.log"
DEFAULT_ERROR_LOG_FILE = "velocity_claw_errors.log"


def _resolve_level(level_name: str | None = None) -> int:
    value = (level_name or os.getenv("LOG_LEVEL", "INFO")).upper()
    level = logging.getLevelName(value)
    return level if isinstance(level, int) else logging.INFO


def _resolve_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _build_formatter() -> logging.Formatter:
    return logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)


def configure_logging(
    *,
    level_name: str | None = None,
    log_dir: str | Path | None = None,
    enable_file: bool | None = None,
    max_bytes: int | None = None,
    backup_count: int | None = None,
) -> logging.Logger:
    """Configure root logging once and return the root logger."""
    root = logging.getLogger()
    level = _resolve_level(level_name)
    root.setLevel(level)

    if _STATE["configured"]:
        for handler in root.handlers:
            handler.setLevel(level)
        return root

    formatter = _build_formatter()
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(level)
    stream_handler.setFormatter(formatter)
    root.addHandler(stream_handler)

    file_logging_enabled = enable_file if enable_file is not None else os.getenv("LOG_TO_FILE", "true").lower() not in {"0", "false", "no", "off"}
    if file_logging_enabled:
        resolved_log_dir = Path(log_dir or os.getenv("LOG_DIR", DEFAULT_LOG_DIR))
        resolved_log_dir.mkdir(parents=True, exist_ok=True)
        resolved_max_bytes = max_bytes or _resolve_int_env("LOG_FILE_MAX_BYTES", 10 * 1024 * 1024)
        resolved_backup_count = backup_count or _resolve_int_env("LOG_FILE_BACKUP_COUNT", 5)

        app_handler = RotatingFileHandler(
            resolved_log_dir / DEFAULT_LOG_FILE,
            maxBytes=resolved_max_bytes,
            backupCount=resolved_backup_count,
            encoding="utf-8",
        )
        app_handler.setLevel(level)
        app_handler.setFormatter(formatter)
        root.addHandler(app_handler)

        error_handler = RotatingFileHandler(
            resolved_log_dir / DEFAULT_ERROR_LOG_FILE,
            maxBytes=resolved_max_bytes,
            backupCount=resolved_backup_count,
            encoding="utf-8",
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        root.addHandler(error_handler)

    _STATE["configured"] = True
    return root


def get_logger(name: str) -> logging.Logger:
    """Return a logger after ensuring centralized logging is configured."""
    configure_logging()
    return logging.getLogger(name)


def reset_logging_for_tests() -> None:
    """Reset root handlers so tests can assert logging setup deterministically."""
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()
    _STATE["configured"] = False
