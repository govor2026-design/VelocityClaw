from __future__ import annotations

import subprocess
import sys


def test_python_m_velocity_claw_displays_help() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "velocity_claw", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "Velocity Claw AI Agent" in completed.stdout


def test_scripts_package_is_importable() -> None:
    import scripts

    assert scripts.__doc__
