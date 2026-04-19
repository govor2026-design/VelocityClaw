import tempfile
import textwrap
import unittest
from pathlib import Path

from velocity_claw.config.settings import Settings
from velocity_claw.tools.patch import PatchEngine
from velocity_claw.tools.code_nav import CodeNavigationTool
from velocity_claw.tools.test_runner import TestRunnerTool
from velocity_claw.executor.executor import Executor
from velocity_claw.models.router import ModelRouter


class PatchEngineTests(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self.settings = Settings(workspace_root=self.workspace)
        self.engine = PatchEngine(self.settings)

    def test_replace_block_preview_and_apply(self):
        path = Path(self.workspace) / "sample.py"
        path.write_text("print('old')\n")
        patch = {"op": "replace_block", "path": "sample.py", "target": "print('old')", "replacement": "print('new')"}
        preview = self.engine.preview(patch)
        self.assertIn("print('new')", preview["diff"])
        result = self.engine.apply(patch)
        self.assertTrue(result["changed"])
        self.assertIn("print('new')", path.read_text())

    def test_replace_function(self):
        path = Path(self.workspace) / "mod.py"
        path.write_text("def hello():\n    return 'old'\n")
        patch = {"op": "replace_function", "path": "mod.py", "name": "hello", "replacement": "def hello():\n    return 'new'"}
        self.engine.apply(patch)
        self.assertIn("return 'new'", path.read_text())

    def test_dry_run_does_not_modify_file(self):
        path = Path(self.workspace) / "mod.py"
        path.write_text("def hello():\n    return 'old'\n")
        patch = {"op": "replace_block", "path": "mod.py", "target": "old", "replacement": "new"}
        result = self.engine.apply(patch, dry_run=True)
        self.assertTrue(result["preview_only"])
        self.assertIn("old", path.read_text())


class CodeNavigationTests(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self.settings = Settings(workspace_root=self.workspace)
        self.nav = CodeNavigationTool(self.settings)
        Path(self.workspace, "nav.py").write_text(textwrap.dedent(
            """
            import os
            from pathlib import Path

            class Demo:
                pass

            def hello():
                return 'ok'
            """
        ))

    def test_find_and_read_symbol(self):
        matches = self.nav.find_symbol("hello", "function")
        self.assertEqual(len(matches), 1)
        symbol = self.nav.read_symbol("nav.py", "hello", "function")
        self.assertIn("return 'ok'", symbol["source"])

    def test_list_imports(self):
        imports = self.nav.list_imports("nav.py")
        self.assertEqual(len(imports), 2)


class TestRunnerTests(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self.settings = Settings(workspace_root=self.workspace)
        self.runner = TestRunnerTool(self.settings)
        Path(self.workspace, "test_sample.py").write_text(textwrap.dedent(
            """
            def test_ok():
                assert 1 == 1
            """
        ))
        Path(self.workspace, "test_fail.py").write_text(textwrap.dedent(
            """
            def test_bad():
                assert 1 == 2
            """
        ))

    def test_run_pytest_success(self):
        result = self.runner.run("pytest", target="test_sample.py", timeout=30)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["summary"]["passed"], 1)

    def test_parse_failures(self):
        result = self.runner.run("pytest", target="test_fail.py", timeout=30)
        self.assertEqual(result["status"], "failed")
        self.assertTrue(result["parsed_failures"])


class ExecutorStage1Tests(unittest.IsolatedAsyncioTestCase):
    async def test_executor_supports_patch_and_dry_run_test(self):
        workspace = tempfile.mkdtemp()
        settings = Settings(workspace_root=workspace, dry_run=True)
        Path(workspace, "sample.py").write_text("print('old')\n")
        executor = Executor(ModelRouter(settings), settings=settings)

        patch_result = await executor.execute_step({
            "id": 1,
            "title": "preview patch",
            "tool": "patch.apply",
            "args": {"patch": {"op": "replace_block", "path": "sample.py", "target": "old", "replacement": "new"}},
        }, {})
        self.assertEqual(patch_result["status"], "success")
        self.assertTrue(patch_result["result"]["preview_only"])

        test_result = await executor.execute_step({
            "id": 2,
            "title": "dry run tests",
            "tool": "test.run",
            "args": {"runner": "pytest", "target": "sample.py"},
        }, {})
        self.assertEqual(test_result["result"]["status"], "simulated")


if __name__ == "__main__":
    unittest.main()
