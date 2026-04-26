import re
from pathlib import Path

from velocity_claw.__version__ import __product_name__, __release_stage__, __version__


def test_version_file_matches_package_metadata():
    version_file = Path("VERSION").read_text(encoding="utf-8").strip()
    assert version_file == __version__
    assert re.match(r"^\d+\.\d+\.\d+$", __version__)


def test_package_release_metadata_shape():
    assert __product_name__ == "Velocity Claw"
    assert __release_stage__ in {"alpha", "beta", "stable"}


def test_release_guide_documents_required_checks():
    content = Path("docs/RELEASE.md").read_text(encoding="utf-8")
    assert "VERSION" in content
    assert "velocity_claw/__version__.py" in content
    assert "CI is green" in content
    assert "release readiness" in content
    assert "Blocking conditions" in content
    assert "semantic versioning" in content
