import unittest
from velocity_claw.tools.fs import FileSystemTool
from velocity_claw.tools.editor import EditorTool


class ToolsSmokeTest(unittest.TestCase):
    def test_file_system_read_write(self):
        fs = FileSystemTool()
        fs.write("tests/tmp_test.txt", "ok")
        data = fs.read("tests/tmp_test.txt")
        self.assertEqual(data, "ok")

    def test_editor_json(self):
        editor = EditorTool()
        data = editor.parse_json('{"ok": true}')
        self.assertEqual(data["ok"], True)


if __name__ == "__main__":
    unittest.main()
