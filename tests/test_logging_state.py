import logging

from velocity_claw.logs import logger


def test_logging_configuration_state_is_scalar_and_resettable() -> None:
    logger.reset_logging_for_tests()

    assert logger._CONFIGURED is False

    first_root = logger.configure_logging(enable_file=False)
    first_handlers = list(first_root.handlers)

    assert logger._CONFIGURED is True
    assert len(first_handlers) == 1

    second_root = logger.configure_logging(enable_file=False)

    assert second_root is first_root
    assert second_root.handlers == first_handlers

    logger.reset_logging_for_tests()

    assert logger._CONFIGURED is False
    assert logging.getLogger().handlers == []
