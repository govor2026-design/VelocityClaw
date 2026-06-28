import logging
from pathlib import Path

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
