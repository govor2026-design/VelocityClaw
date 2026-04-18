import unittest
import tempfile
from pathlib import Path
from velocity_claw.config.settings import Settings
from velocity_claw.tools.fs import FileSystemTool
from velocity_claw.tools.shell import ShellTool
from velocity_claw.tools.git import GitTool


class SecurityTests(unittest.TestCase):
    def setUp(self):
        self.settings = Settings(workspace_root=tempfile.mkdtemp())

    def test_shell_blocks_dangerous_commands(self):
        shell = ShellTool(self.settings)
        with self.assertRaises(ValueError):
            shell.validate_command("rm -rf /")
        with self.assertRaises(ValueError):
            shell.validate_command("sudo apt update")

    def test_shell_allowlist_restricts_powerful_commands(self):
        shell = ShellTool(self.settings)
        for command in ["python3 -V", "pip list", "docker ps", "curl https://example.com", "wget https://example.com"]:
            with self.assertRaises(ValueError):
                shell.validate_command(command)

    def test_shell_allows_safe_commands(self):
        shell = ShellTool(self.settings)
        args = shell.validate_command("ls -la")
        self.assertEqual(args, ["ls", "-la"])

    def test_git_blocks_destructive_commands(self):
        git = GitTool(self.settings)
        with self.assertRaises(ValueError):
            git.validate_git_command("git reset --hard")
        with self.assertRaises(ValueError):
            git.validate_git_command("git clean -fd")

    def test_fs_blocks_path_traversal(self):
        fs = FileSystemTool(self.settings)
        with self.assertRaises(ValueError):
            fs._validate_path("../outside.txt")
        with self.assertRaises(ValueError):
            fs._validate_path("/etc/passwd")

    def test_fs_allows_workspace_paths(self):
        fs = FileSystemTool(self.settings)
        resolved = fs._validate_path("test.txt")
        self.assertTrue(str(resolved).startswith(str(Path(self.settings.workspace_root).resolve())))


class ToolTests(unittest.TestCase):
    def setUp(self):
        self.settings = Settings(workspace_root=tempfile.mkdtemp())

    def test_fs_read_write(self):
        fs = FileSystemTool(self.settings)
        fs.write("test.txt", "content")
        content = fs.read("test.txt")
        self.assertEqual(content, "content")

    def test_fs_replace(self):
        fs = FileSystemTool(self.settings)
        fs.write("test.txt", "old content")
        fs.replace("test.txt", "old", "new")
        content = fs.read("test.txt")
        self.assertEqual(content, "new content")

    def test_shell_run_safe_command(self):
        shell = ShellTool(self.settings)
        result = shell.run_command("echo hello", cwd=self.settings.workspace_root)
        self.assertEqual(result["code"], 0)
        self.assertIn("hello", result["stdout"])


if __name__ == "__main__":
    unittest.main()
