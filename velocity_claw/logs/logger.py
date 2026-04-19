"""
Logging layer for VelocityClaw.

Provides get_logger(name) — a thin wrapper around the standard library
logging module that:
- reads LOG_LEVEL from settings/env (default INFO)
- attaches a StreamHandler only once (no duplicate handlers)
- is safe to call multiple times with the same name
- works in CLI, API, and test contexts
"""

import logging
import os

_HANDLER_ATTACHED: set[str] = set()

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"


def _resolve_level() -> int:
    """Read LOG_LEVEL from environment, fall back to INFO."""
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = logging.getLevelName(level_name)
    # getLevelName returns the string itself if unknown; fall back to INFO
    if not isinstance(level, int):
        level = logging.INFO
    return level


def get_logger(name: str) -> logging.Logger:
    """
    Return a configured logger for *name*.

    A StreamHandler is added to the root logger the first time this function
    is called, and never added again — so importing this module from multiple
    files does not produce duplicate log lines.
    """
    root = logging.getLogger()

    if "root" not in _HANDLER_ATTACHED:
        level = _resolve_level()
        root.setLevel(level)

        handler = logging.StreamHandler()
        handler.setLevel(level)
        formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)
        handler.setFormatter(formatter)
        root.addHandler(handler)

        _HANDLER_ATTACHED.add("root")

    logger = logging.getLogger(name)
    return logger
