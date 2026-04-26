import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import cli
from velocity_claw.config.settings import Settings
from velocity_claw.core.agent import VelocityClawAgent


class OperatorCliAdminCommandsV2Tests(unittest.TestCase):
    def make_settings(self):
        workspace = tempfile.mkdtemp()
        db_path = str(Path(workspace) / "memory.db")
        return Settings(workspace_root=workspace, memory_db_path=db_path)

    def test_print_payload_json(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            cli._print_payload({"status": "ok"}, as_json=True)
        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload["status"], "ok")

    def test_status_cli_json(self):
        settings = self.make_settings()
        with patch("cli.load_settings", return_value=settings):
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                cli.main_args = None
                agent = cli.build_agent()
                cli._print_payload(agent.get_status(), as_json=True)
        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload["status"], "ready")
        self.assertIn("available_modes", payload)

    def test_list_runs_cli_json(self):
        settings = self.make_settings()
        agent = VelocityClawAgent(settings)
        agent.memory.create_run("demo task")
        with patch("cli.build_agent", return_value=agent):
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                cli.list_runs_cli(limit=5, as_json=True)
        payload = json.loads(buffer.getvalue())
        self.assertEqual(len(payload["runs"]), 1)
        self.assertEqual(payload["runs"][0]["task"], "demo task")

    def test_retry_context_cli_json(self):
        settings = self.make_settings()
        agent = VelocityClawAgent(settings)
        run_id = agent.memory.create_run("fix tests")
        agent.memory.save_step(run_id, {
            "id": 1,
            "title": "run tests",
            "tool": "test.run",
            "args": {},
            "status": "failed",
            "result": None,
            "error": "boom",
            "started_at": "2026-04-26T00:00:00",
            "completed_at": "2026-04-26T00:00:01",
        })
        agent.memory.update_run_status(run_id, "failed")
        with patch("cli.build_agent", return_value=agent):
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                cli.retry_context_cli(run_id, as_json=True)
        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload["retry"]["source_run_id"], run_id)
        self.assertEqual(payload["retry"]["recommended_strategy"]["mode"], "inspect_failed_step_first")


if __name__ == "__main__":
    unittest.main()
