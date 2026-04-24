import tempfile
import unittest
from pathlib import Path

from velocity_claw.config.settings import Settings
from velocity_claw.tools.patch import PatchEngine, PatchError


class PatchV2Tests(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self.settings = Settings(workspace_root=self.workspace)
        self.engine = PatchEngine(self.settings)
        Path(self.workspace, "sample.py").write_text("def foo():\n    return 1\n", encoding="utf-8")

    def test_replace_block_same_text_rejected(self):
        with self.assertRaises(PatchError):
            self.engine.apply({
                "op": "replace_block",
                "path": "sample.py",
                "target": "return 1",
                "replacement": "return 1",
            })

    def test_replace_block_empty_text_rejected(self):
        with self.assertRaises(PatchError):
            self.engine.apply({
                "op": "replace_block",
                "path": "sample.py",
                "target": "return 1",
                "replacement": "",
            })

    def test_append_empty_text_rejected(self):
        with self.assertRaises(PatchError):
            self.engine.apply({
                "op": "append",
                "path": "sample.py",
                "content": "",
            })

    def test_preview_has_richer_details(self):
        result = self.engine.preview({
            "op": "replace_function",
            "path": "sample.py",
            "name": "foo",
            "replacement": "def foo():\n    return 2\n",
        })
        self.assertTrue(result["changed"])
        self.assertIn("symbol_kind", result["details"])
        self.assertIn("replacement_bytes", result["details"])


if __name__ == "__main__":
    unittest.main()
