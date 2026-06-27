import inspect

from velocity_claw.core.runtime import _handle_signal


def test_signal_handler_marks_frame_argument_as_intentionally_unused() -> None:
    parameters = list(inspect.signature(_handle_signal).parameters)

    assert parameters == ["signum", "_frame"]
