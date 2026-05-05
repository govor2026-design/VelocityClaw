import logging
from pathlib import Path

from velocity_claw.logs.logger import configure_logging, get_logger, reset_logging_for_tests


def teardown_function():
    reset_logging_for_tests()


def test_configure_logging_adds_stream_app_and_error_handlers(tmp_path):
    reset_logging_for_tests()
    root = configure_logging(log_dir=tmp_path, enable_file=True, max_bytes=1024, backup_count=1)
    assert len(root.handlers) == 3
    assert (tmp_path / "velocity_claw.log").exists()
    assert (tmp_path / "velocity_claw_errors.log").exists()


def test_configure_logging_is_idempotent(tmp_path):
    reset_logging_for_tests()
    root = configure_logging(log_dir=tmp_path, enable_file=True)
    first_handler_ids = [id(handler) for handler in root.handlers]
    root = configure_logging(log_dir=tmp_path, enable_file=True)
    second_handler_ids = [id(handler) for handler in root.handlers]
    assert first_handler_ids == second_handler_ids


def test_get_logger_writes_to_rotating_file(tmp_path, monkeypatch):
    reset_logging_for_tests()
    monkeypatch.setenv("LOG_DIR", str(tmp_path))
    logger = get_logger("velocity_claw.test")
    logger.info("centralized logging smoke test")
    for handler in logging.getLogger().handlers:
        handler.flush()
    content = (tmp_path / "velocity_claw.log").read_text(encoding="utf-8")
    assert "centralized logging smoke test" in content
    assert "velocity_claw.test" in content


def test_invalid_log_level_falls_back_to_info(tmp_path):
    reset_logging_for_tests()
    root = configure_logging(level_name="NOPE", log_dir=tmp_path, enable_file=False)
    assert root.level == logging.INFO
