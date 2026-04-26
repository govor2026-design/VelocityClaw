from pathlib import Path


def test_ci_runs_package_metadata_validator_before_tests():
    content = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "Validate package metadata" in content
    assert "python scripts/validate_package.py" in content
    assert content.index("Validate package metadata") < content.index("Run tests")
