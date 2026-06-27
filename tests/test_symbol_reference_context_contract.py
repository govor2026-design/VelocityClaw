from pathlib import Path

from velocity_claw.config.settings import Settings
from velocity_claw.tools.code_nav import CodeNavigationTool


def test_find_references_uses_reference_definition_and_import_contexts(tmp_path: Path) -> None:
    (tmp_path / "sample.py").write_text(
        "from module import target\n\n"
        "def target():\n"
        "    return 1\n\n"
        "value = target()\n",
        encoding="utf-8",
    )
    nav = CodeNavigationTool(Settings(workspace_root=str(tmp_path)))

    contexts = {item["context"] for item in nav.find_references("target")}

    assert contexts == {"import", "definition", "reference"}
