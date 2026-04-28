from pathlib import Path

from scripts.generate_release_notes import generate_release_notes, write_release_notes


def test_generate_release_notes_mentions_version_and_release_areas():
    notes = generate_release_notes(Path.cwd())
    version = Path("VERSION").read_text(encoding="utf-8").strip()
    assert f"Velocity Claw v{version}" in notes
    assert "Release readiness checklist" in notes
    assert "Systemd deployment" in notes
    assert "Docker Compose deployment" in notes
    assert "production installer" in notes
    assert "build-artifacts" in notes


def test_generate_release_notes_checks_core_docs_and_workflows():
    notes = generate_release_notes(Path.cwd())
    assert "[x] deployment guide" in notes
    assert "[x] release guide" in notes
    assert "[x] pyproject" in notes
    assert "[x] release workflow" in notes
    assert "[x] build artifact workflow" in notes


def test_write_release_notes_creates_output_file(tmp_path):
    output = tmp_path / "release-notes.md"
    written = write_release_notes(Path.cwd(), output)
    assert written == output
    assert output.exists()
    assert "Velocity Claw" in output.read_text(encoding="utf-8")
