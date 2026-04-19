import tempfile
import unittest
from pathlib import Path

from velocity_claw.api.server import create_app
from velocity_claw.config.settings import Settings
from velocity_claw.core.agent import VelocityClawAgent
from velocity_claw.core.modes import build_mode_task
from velocity_claw.core.queue import RunQueue


class ModesTests(unittest.TestCase):
    def test_build_mode_task(self):
        result = build_mode_task("analyze_repo", "check repo")
        self.assertIn("[analyze_repo]", result)
        self.assertIn("check repo", result)


class QueueTests(unittest.IsolatedAsyncioTestCase):
    async def test_queue_runs_job(self):
        queue = RunQueue()
        job = queue.enqueue("task")

        async def runner(task, context):
            return {"task": task, "status": "completed"}

        await queue.run_job(job.job_id, runner)
        self.assertEqual(queue.get(job.job_id).status, "completed")


class DashboardAndApprovalsTests(unittest.IsolatedAsyncioTestCase):
    async def test_agent_can_create_pending_approval_and_memory_lists_it(self):
        workspace = tempfile.mkdtemp()
        db_path = str(Path(workspace) / "memory.db")
        settings = Settings(workspace_root=workspace, memory_db_path=db_path, execution_profile="safe")
        Path(workspace, "sample.py").write_text("print('old')\n")
        agent = VelocityClawAgent(settings)

        async def fake_plan(task, context=None):
            return {
                "task": task,
                "steps": [
                    {"id": 1, "title": "patch", "tool": "patch.apply", "args": {"patch": {"op": "replace_block", "path": "sample.py", "target": "old", "replacement": "new"}}, "expected_output": "patched"}
                ],
            }
        agent.planner.create_plan = fake_plan
        result = await agent.run_task("patch")
        self.assertEqual(result["steps"][0]["status"], "pending_approval")
        self.assertTrue(agent.list_pending_approvals())

    def test_create_app_dashboard_and_metrics(self):
        app = create_app()
        self.assertTrue(hasattr(app.state, "queue"))
        self.assertTrue(hasattr(app.state, "metrics"))
