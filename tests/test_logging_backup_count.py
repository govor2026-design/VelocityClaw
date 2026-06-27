from logging.handlers import RotatingFileHandler

from velocity_claw.logs.logger import configure_logging, reset_logging_for_tests


def test_configure_logging_preserves_zero_backup_count(tmp_path) -> None:
    reset_logging_for_tests()
    try:
        root = configure_logging(
            enable_file=True,
            log_dir=tmp_path,
            backup_count=0,
        )

        rotating_handlers = [
            handler for handler in root.handlers if isinstance(handler, RotatingFileHandler)
        ]

        assert rotating_handlers
        assert all(handler.backupCount == 0 for handler in rotating_handlers)
    finally:
        reset_logging_for_tests()
