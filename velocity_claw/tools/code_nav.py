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
                entry = self._build_entry(node, rel, source)
                if not entry:
                    continue
                if entry["name"] == name and (kind is None or entry["kind"] == kind):
                    matches.append(entry)
        return sorted(matches, key=lambda m: (-m["match_score"], m["path"], m["line_start"]))

    def read_symbol(self, path: str, name: str, kind: str) -> dict:
        source = self.fs.read(path)
        tree = ast.parse(source)
        lines = source.splitlines(keepends=True)
        matches = []
        for node in ast.walk(tree):
            entry = self._build_entry(node, path, source)
            if entry and entry["kind"] == kind and entry["name"] == name:
                matches.append((node, entry))
        if not matches:
            raise ValueError(f"{kind} '{name}' not found")
        if len(matches) > 1:
            raise ValueError(f"ambiguous {kind} '{name}'")
        node, entry = matches[0]
        return {
            **entry,
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

    def find_references(self, name: str) -> List[dict]:
        refs: List[dict] = []
        for path in self.workspace_root.rglob("*.py"):
            rel = str(path.relative_to(self.workspace_root))
            try:
                source = self.fs.read(rel)
                tree = ast.parse(source)
            except Exception:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Name) and node.id == name:
                    refs.append({
                        "path": rel,
                        "name": name,
                        "line": node.lineno,
                        "column": node.col_offset,
                        "context": "reference",
                    })
        return sorted(refs, key=lambda r: (r["path"], r["line"], r["column"]))

    def explain_ambiguity(self, name: str, kind: Optional[str] = None) -> dict:
        matches = self.find_symbol(name, kind)
        return {
            "name": name,
            "kind": kind,
            "count": len(matches),
            "matches": matches,
            "ambiguous": len(matches) > 1,
        }

    def _build_entry(self, node: ast.AST, path: str, source: str) -> Optional[dict]:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return {
                "path": path,
                "kind": "function",
                "name": node.name,
                "line_start": node.lineno,
                "line_end": node.end_lineno,
                "is_async": isinstance(node, ast.AsyncFunctionDef),
                "decorator_count": len(node.decorator_list),
                "docstring": ast.get_docstring(node),
                "match_score": 100,
            }
        if isinstance(node, ast.ClassDef):
            return {
                "path": path,
                "kind": "class",
                "name": node.name,
                "line_start": node.lineno,
                "line_end": node.end_lineno,
                "is_async": False,
                "decorator_count": len(node.decorator_list),
                "docstring": ast.get_docstring(node),
                "match_score": 100,
            }
        return None
