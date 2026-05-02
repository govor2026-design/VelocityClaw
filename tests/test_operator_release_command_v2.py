import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import cli
from velocity_claw.config.settings import Settings


def test_validate_package_cli_json_outputs_package_status():
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        cli.validate_package_cli(as_json=True)
    payload = json.loads(buffer.getvalue())
    assert payload["status"] == "ok"
    assert payload["name"] == "velocity-claw"
    assert payload["version"] == Path("VERSION").read_text(encoding="utf-8").strip()


def test_generate_release_notes_cli_json_outputs_path(tmp_path):
    with patch("cli.Path.cwd", return_value=Path.cwd()):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            cli.generate_release_notes_cli(as_json=True)
    payload = json.loads(buffer.getvalue())
    assert payload["status"] == "ok"
    assert payload["path"].endswith("dist/release-notes.md")
    assert Path(payload["path"]).exists()


def test_release_checklist_cli_json_combines_package_readiness_and_notes(tmp_path):
    settings = Settings(workspace_root=str(tmp_path), memory_db_path=str(tmp_path / "memory.db"))
    with patch("cli.load_settings", return_value=settings):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            cli.release_checklist_cli(as_json=True)
    payload = json.loads(buffer.getvalue())
    assert payload["status"] == "ok"
    assert payload["package_validation"]["status"] == "ok"
    assert "release_readiness" in payload
    assert payload["release_notes_path"].endswith("dist/release-notes.md")
