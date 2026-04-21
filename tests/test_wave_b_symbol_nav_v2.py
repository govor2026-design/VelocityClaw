import tempfile
import textwrap
import unittest
from pathlib import Path

from velocity_claw.config.settings import Settings
from velocity_claw.tools.code_nav import CodeNavigationTool


class SymbolNavigationV2Tests(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self.settings = Settings(workspace_root=self.workspace)
        self.nav = CodeNavigationTool(self.settings)
        Path(self.workspace, "a.py").write_text(textwrap.dedent(
            """
            class Demo:
                """demo class"""
                pass

            def hello():
                """hello doc"""
                value = 1
                return value
            """
        ))
        Path(self.workspace, "b.py").write_text(textwrap.dedent(
            """
            def hello():
                return 2
            """
        ))

    def test_find_symbol_has_metadata(self):
        matches = self.nav.find_symbol("hello", "function")
        self.assertTrue(matches)
        self.assertIn("docstring", matches[0])
        self.assertIn("match_score", matches[0])

    def test_find_references(self):
        refs = self.nav.find_references("value")
        self.assertTrue(refs)
        self.assertEqual(refs[0]["context"], "reference")

    def test_explain_ambiguity(self):
        info = self.nav.explain_ambiguity("hello", "function")
        self.assertTrue(info["ambiguous"])
        self.assertEqual(info["count"], 2)


if __name__ == "__main__":
    unittest.main()
