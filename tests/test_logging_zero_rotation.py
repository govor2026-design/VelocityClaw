import logging

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
