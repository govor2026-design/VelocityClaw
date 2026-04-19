from __future__ import annotations

import ast
from pathlib import Path
from typing import List, Optional

from velocity_claw.config.settings import Settings
from velocity_claw.tools.fs import FileSystemTool


class CodeNavigationTool:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.fs = FileSystemTool(settings)
        self.workspace_root = Path(settings.workspace_root).resolve()

    def find_symbol(self, name: str, kind: Optional[str] = None) -> List[dict]:
        matches: List[dict] = []
        for path in self.workspace_root.rglob("*.py"):
            rel = str(path.relative_to(self.workspace_root))
            try:
                source = self.fs.read(rel)
                tree = ast.parse(source)
            except Exception:
                continue
            for node in ast.walk(tree):
                entry = None
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
                    entry = {
                        "path": rel,
                        "kind": "function",
                        "name": node.name,
                        "line_start": node.lineno,
                        "line_end": node.end_lineno,
                    }
                elif isinstance(node, ast.ClassDef) and node.name == name:
                    entry = {
                        "path": rel,
                        "kind": "class",
                        "name": node.name,
                        "line_start": node.lineno,
                        "line_end": node.end_lineno,
                    }
                if entry and (kind is None or entry["kind"] == kind):
                    matches.append(entry)
        return sorted(matches, key=lambda m: (m["path"], m["line_start"]))

    def read_symbol(self, path: str, name: str, kind: str) -> dict:
        source = self.fs.read(path)
        tree = ast.parse(source)
        lines = source.splitlines(keepends=True)
        matches = []
        for node in ast.walk(tree):
            if kind == "function" and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
                matches.append(node)
            elif kind == "class" and isinstance(node, ast.ClassDef) and node.name == name:
                matches.append(node)
        if not matches:
            raise ValueError(f"{kind} '{name}' not found")
        if len(matches) > 1:
            raise ValueError(f"ambiguous {kind} '{name}'")
        node = matches[0]
        return {
            "path": path,
            "kind": kind,
            "name": name,
            "line_start": node.lineno,
            "line_end": node.end_lineno,
            "source": "".join(lines[node.lineno - 1: node.end_lineno]),
        }

    def list_imports(self, path: str) -> List[dict]:
        source = self.fs.read(path)
        tree = ast.parse(source)
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append({
                        "type": "import",
                        "module": alias.name,
                        "alias": alias.asname,
                        "line": node.lineno,
                    })
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    imports.append({
                        "type": "from_import",
                        "module": node.module,
                        "name": alias.name,
                        "alias": alias.asname,
                        "line": node.lineno,
                    })
        return sorted(imports, key=lambda x: x["line"])
