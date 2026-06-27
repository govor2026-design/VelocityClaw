from velocity_claw.logs import logger as logger_module


def test_logging_configuration_state_is_owned_by_root_logger() -> None:
    logger_module.reset_logging_for_tests()

    root = logger_module.configure_logging(enable_file=False)

    assert not hasattr(logger_module, "_CONFIGURED")
    assert getattr(root, "_velocity_claw_configured") is True
    assert len(root.handlers) == 1

    logger_module.configure_logging(enable_file=False)
    assert len(root.handlers) == 1

    logger_module.reset_logging_for_tests()
    assert not hasattr(root, "_velocity_claw_configured")
    assert root.handlers == []
