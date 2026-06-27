from __future__ import annotations

import signal
from dataclasses import dataclass, field
from types import FrameType
from typing import Callable, Optional, TypeVar

from velocity_claw.logs.logger import get_logger

T = TypeVar("T")


@dataclass
class ShutdownState:
    requested: bool = False
    signals: list[str] = field(default_factory=list)

    def request(self, signal_name: str = "manual") -> None:
        self.requested = True
        self.signals.append(signal_name)


shutdown_state = ShutdownState()


def _handle_signal(signum: int, _frame: Optional[FrameType]) -> None:
    signal_name = signal.Signals(signum).name
    shutdown_state.request(signal_name)
    get_logger("velocity_claw.runtime").warning("Shutdown requested by %s", signal_name)


def install_shutdown_handlers() -> ShutdownState:
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, _handle_signal)
    return shutdown_state


def run_with_exception_boundary(action: Callable[[], T], *, component: str = "runtime") -> int:
    logger = get_logger(f"velocity_claw.{component}")
    install_shutdown_handlers()
    try:
        action()
        return 0
    except KeyboardInterrupt:
        shutdown_state.request("KeyboardInterrupt")
        logger.warning("%s interrupted; shutting down gracefully", component)
        return 130
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
        logger.info("%s exited with code %s", component, code)
        return code
    except Exception as exc:
        logger.exception("Unhandled %s exception: %s", component, exc)
        return 1


def exit_with_boundary(action: Callable[[], T], *, component: str = "runtime") -> None:
    raise SystemExit(run_with_exception_boundary(action, component=component))
