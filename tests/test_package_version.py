from pathlib import Path

import velocity_claw
from velocity_claw.__version__ import __version__ as canonical_version


def test_package_exports_canonical_version() -> None:
    assert velocity_claw.__version__ == canonical_version


def test_version_file_matches_package_version() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    version_file = (repository_root / "VERSION").read_text(encoding="utf-8").strip()

    assert version_file == canonical_version
