import signal

from velocity_claw.core import runtime
from velocity_claw.core.runtime import ShutdownState, run_with_exception_boundary


def test_run_with_exception_boundary_returns_zero_on_success(monkeypatch):
    monkeypatch.setattr(runtime, "install_shutdown_handlers", lambda: runtime.shutdown_state)
    assert run_with_exception_boundary(lambda: None, component="test") == 0


def test_run_with_exception_boundary_handles_keyboard_interrupt(monkeypatch):
    state = ShutdownState()
    monkeypatch.setattr(runtime, "shutdown_state", state)
    monkeypatch.setattr(runtime, "install_shutdown_handlers", lambda: state)

    def action():
        raise KeyboardInterrupt()

    assert run_with_exception_boundary(action, component="test") == 130
    assert state.requested is True
    assert "KeyboardInterrupt" in state.signals


def test_run_with_exception_boundary_handles_unhandled_exception(monkeypatch):
    monkeypatch.setattr(runtime, "install_shutdown_handlers", lambda: runtime.shutdown_state)

    def action():
        raise RuntimeError("boom")

    assert run_with_exception_boundary(action, component="test") == 1


def test_run_with_exception_boundary_preserves_system_exit_code(monkeypatch):
    monkeypatch.setattr(runtime, "install_shutdown_handlers", lambda: runtime.shutdown_state)

    def action():
        raise SystemExit(7)

    assert run_with_exception_boundary(action, component="test") == 7


def test_signal_handler_marks_shutdown_requested(monkeypatch):
    state = ShutdownState()
    monkeypatch.setattr(runtime, "shutdown_state", state)
    runtime._handle_signal(signal.SIGTERM, None)
    assert state.requested is True
    assert "SIGTERM" in state.signals
