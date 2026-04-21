import tempfile
import unittest
from pathlib import Path

from velocity_claw.config.settings import Settings
from velocity_claw.memory.store import MemoryStore


class RepoAwareMemoryV2Tests(unittest.TestCase):
    def test_repo_context_summary_includes_notes_and_facts(self):
        workspace = tempfile.mkdtemp()
        db_path = str(Path(workspace) / "memory.db")
        settings = Settings(workspace_root=workspace, memory_db_path=db_path)
        store = MemoryStore(settings)
        store.save_project_fact("framework", {"name": "python"})
        store.save_project_note("task", "improve queue")
        summary = store.build_repo_context_summary()
        self.assertIn("project_facts", summary)
        self.assertIn("recent_notes", summary)
        self.assertEqual(summary["project_facts"]["framework"]["name"], "python")
        self.assertTrue(summary["recent_notes"])


if __name__ == "__main__":
    unittest.main()
