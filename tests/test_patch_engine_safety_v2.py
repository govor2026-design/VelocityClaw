import tempfile
import unittest
from pathlib import Path

from velocity_claw.config.settings import Settings
from velocity_claw.tools.patch import PatchEngine, PatchError


class PatchEngineSafetyV2Tests(unittest.TestCase):
    def test_insert_ambiguous_anchor_fails(self):
        workspace = tempfile.mkdtemp()
        Path(workspace, "sample.py").write_text("hello\nhello\n")
        engine = PatchEngine(Settings(workspace_root=workspace))
        with self.assertRaises(PatchError) as ctx:
            engine.apply({"op": "insert", "path": "sample.py", "anchor": "hello", "content": "X"})
        self.assertIn("ambiguous anchor match", str(ctx.exception))

    def test_binary_file_is_rejected(self):
        workspace = tempfile.mkdtemp()
        Path(workspace, "sample.bin").write_bytes(b"\x00\xff\x00\xff")
        engine = PatchEngine(Settings(workspace_root=workspace))
        with self.assertRaises(PatchError) as ctx:
            engine.apply({"op": "append", "path": "sample.bin", "content": "text"})
        self.assertIn("binary file", str(ctx.exception))

    def test_file_too_large_is_rejected(self):
        workspace = tempfile.mkdtemp()
        content = "a" * 32
        Path(workspace, "sample.txt").write_text(content)
        engine = PatchEngine(Settings(workspace_root=workspace, max_file_size=8))
        with self.assertRaises(PatchError) as ctx:
            engine.apply({"op": "append", "path": "sample.txt", "content": "b"})
        self.assertIn("file too large", str(ctx.exception))

    def test_details_include_match_diagnostics(self):
        workspace = tempfile.mkdtemp()
        Path(workspace, "sample.py").write_text("hello\n")
        engine = PatchEngine(Settings(workspace_root=workspace))
        result = engine.preview({"op": "insert", "path": "sample.py", "anchor": "hello", "content": " world"})
        self.assertEqual(result["details"]["anchor_matches"], 1)
        self.assertEqual(result["details"]["position"], "after")


if __name__ == "__main__":
    unittest.main()
