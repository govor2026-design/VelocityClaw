from pathlib import Path

import velocity_claw
from velocity_claw.__version__ import (
    __product_name__ as canonical_product_name,
    __release_stage__ as canonical_release_stage,
    __version__ as canonical_version,
)


def test_package_exports_canonical_metadata() -> None:
    assert velocity_claw.__version__ == canonical_version
    assert velocity_claw.__release_stage__ == canonical_release_stage
    assert velocity_claw.__product_name__ == canonical_product_name


def test_version_file_matches_package_version() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    version_file = (repository_root / "VERSION").read_text(encoding="utf-8").strip()

    assert version_file == canonical_version
