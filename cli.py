"""Backward-compatible wrapper for the packaged Velocity Claw CLI."""

from velocity_claw.cli import main
from velocity_claw.core.runtime import exit_with_boundary


if __name__ == "__main__":
    exit_with_boundary(main, component="cli")
