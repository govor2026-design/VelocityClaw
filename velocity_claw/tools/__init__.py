import ast

from velocity_claw.tools.fs import FileSystemTool
from velocity_claw.tools.shell import ShellTool
from velocity_claw.tools.git import GitTool
from velocity_claw.tools.http import HTTPTool
from velocity_claw.tools.patch import PatchEngine
from velocity_claw.tools.code_nav import CodeNavigationTool
from velocity_claw.tools.test_runner import TestRunnerTool


def _install_reference_context_contract(tool_cls: type) -> None:
    if getattr(tool_cls, "_reference_context_contract_installed", False):
        return

    original = tool_cls._reference_entry

    def _reference_entry(self, node, name, path, source_lines):
        entry = original(self, node, name, path, source_lines)
        if entry is not None:
            if isinstance(node, ast.alias):
                entry["context"] = "import"
            else:
                entry["context"] = "reference"
            return entry

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == name:
            line = node.lineno
            source_line = source_lines[line - 1].strip() if 0 < line <= len(source_lines) else ""
            return {
                "path": path,
                "name": name,
                "line": line,
                "column": node.col_offset,
                "context": "definition",
                "source_line": source_line,
            }

        return None

    tool_cls._reference_entry = _reference_entry
    tool_cls._reference_context_contract_installed = True


_install_reference_context_contract(CodeNavigationTool)

__all__ = [
    "FileSystemTool",
    "ShellTool",
    "GitTool",
    "HTTPTool",
    "PatchEngine",
    "CodeNavigationTool",
    "TestRunnerTool",
]
