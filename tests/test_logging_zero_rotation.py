import logging
from pathlib import Path

import pytest

from velocity_claw.logs import logger as logger_module


def test_zero_max_bytes_disables_rotation(monkeypatch, tmp_path) -> None:
    recorded_max_bytes: list[int] = []

    class RecordingHandler(logging.Handler):
        def __init__(self, _filename, *, maxBytes: int, backupCount: int, encoding: str) -> None:
            super().__init__()
            recorded_max_bytes.append(maxBytes)

    logger_module.reset_logging_for_tests()
    monkeypatch.setattr(logger_module, "RotatingFileHandler", RecordingHandler)

    try:
        logger_module.configure_logging(enable_file=True, log_dir=tmp_path, max_bytes=0)
        assert recorded_max_bytes == [0, 0]
    finally:
        logger_module.reset_logging_for_tests()


def test_empty_log_dir_targets_current_directory(monkeypatch, tmp_path) -> None:
    recorded_paths: list[Path] = []

    class RecordingHandler(logging.Handler):
        def __init__(self, filename, *, maxBytes: int, backupCount: int, encoding: str) -> None:
            super().__init__()
            recorded_paths.append(Path(filename))

    logger_module.reset_logging_for_tests()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LOG_DIR", "ignored-log-directory")
    monkeypatch.setattr(logger_module, "RotatingFileHandler", RecordingHandler)

    try:
        logger_module.configure_logging(enable_file=True, log_dir="")
        assert recorded_paths == [Path("velocity_claw.log"), Path("velocity_claw_errors.log")]
    finally:
        logger_module.reset_logging_for_tests()


def test_empty_explicit_level_does_not_use_environment(monkeypatch) -> None:
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    assert logger_module._resolve_level("") == logging.INFO


def test_file_logging_toggle_ignores_surrounding_whitespace(monkeypatch) -> None:
    logger_module.reset_logging_for_tests()
    monkeypatch.setenv("LOG_TO_FILE", " false ")

    try:
        root = logger_module.configure_logging()
        assert not any(isinstance(handler, logger_module.RotatingFileHandler) for handler in root.handlers)
    finally:
        logger_module.reset_logging_for_tests()


def test_log_level_ignores_surrounding_whitespace(monkeypatch) -> None:
    monkeypatch.setenv("LOG_LEVEL", " debug ")

    assert logger_module._resolve_level() == logging.DEBUG


def test_negative_rotation_setting_uses_default(monkeypatch) -> None:
    monkeypatch.setenv("LOG_FILE_BACKUP_COUNT", "-1")

    assert logger_module._resolve_int_env("LOG_FILE_BACKUP_COUNT", 5) == 5


@pytest.mark.parametrize("setting", [{"max_bytes": -1}, {"backup_count": -1}])
def test_explicit_negative_rotation_setting_is_rejected(setting) -> None:
    with pytest.raises(ValueError):
        logger_module.configure_logging(**setting)


def test_reconfigure_preserves_error_only_handler_level(tmp_path) -> None:
    logger_module.reset_logging_for_tests()

    try:
        root = logger_module.configure_logging(enable_file=True, log_dir=tmp_path, level_name="INFO")
        logger_module.configure_logging(level_name="DEBUG")
        error_handlers = [
            handler
            for handler in root.handlers
            if getattr(handler, logger_module._ERROR_HANDLER_ATTR, False)
        ]

        assert len(error_handlers) == 1
        assert error_handlers[0].level == logging.ERROR
    finally:
        logger_module.reset_logging_for_tests()


def test_reconfigure_can_disable_managed_file_handlers(tmp_path) -> None:
    logger_module.reset_logging_for_tests()

    try:
        root = logger_module.configure_logging(enable_file=True, log_dir=tmp_path)
        assert sum(
            bool(getattr(handler, logger_module._FILE_HANDLER_ATTR, False))
            for handler in root.handlers
        ) == 2

        logger_module.configure_logging(enable_file=False)

        assert not any(
            getattr(handler, logger_module._FILE_HANDLER_ATTR, False)
            for handler in root.handlers
        )
        assert any(isinstance(handler, logging.StreamHandler) for handler in root.handlers)
    finally:
        logger_module.reset_logging_for_tests()
