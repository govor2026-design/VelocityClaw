from pathlib import Path


def test_source_distribution_contains_operator_and_deployment_assets():
    manifest = Path("MANIFEST.in").read_text(encoding="utf-8")

    required = [
        "include CHANGELOG.md",
        "include ARCHITECTURE.md",
        "include ISSUE_BACKLOG.md",
        "include RUNBOOK.md",
        "include SECURITY.md",
        "include VERSION",
        "include requirements.txt",
        "include Dockerfile",
        "include cli.py",
        "include .env.example",
        "recursive-include docs *.md",
        "recursive-include deploy *",
        "recursive-include scripts *.py",
        "recursive-include .github/workflows *.yml",
    ]
    for entry in required:
        assert entry in manifest

    assert "global-exclude __pycache__" in manifest
    assert "global-exclude *.py[cod]" in manifest
