from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterable, List, Optional

from velocity_claw.config.settings import Settings
from velocity_claw.tools.fs import FileSystemTool


class CodeNavigationTool:
    IGNORED_DIRECTORIES = {
        ".git",
        ".hg",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        "node_modules",
        "venv",
    }
    HTTP_METHODS = {
        "get",
        "post",
        "put",
        "delete",
        "patch",
        "options",
        "head",
        "websocket",
    }
    MAX_REFERENCE_RESULTS = 1000
    MAX_READ_LINES = 200
    MAX_CONTEXT_LINES = 20

    def __init__(self, settings: Settings):
        self.settings = settings
        self.fs = FileSystemTool(settings)
        self.workspace_root = Path(settings.workspace_root).resolve()

    def find_symbol(self, name: str, kind: Optional[str] = None) -> List[dict]:
        matches: List[dict] = []
        for path in self._python_files():
            rel = self._relative(path)
            parsed = self._parse_for_scan(path)
            if parsed is None:
                continue
            source, tree = parsed
            for node in ast.walk(tree):
                entry = self._build_entry(node, rel, source)
                if not entry:
                    continue
                if entry["name"] == name and (kind is None or entry["kind"] == kind):
                    matches.append(entry)
        return sorted(matches, key=lambda item: (-item["match_score"], item["path"], item["line_start"]))

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

    def read_lines(
        self,
        path: str,
        start_line: int,
        end_line: int,
        context_lines: int = 0,
    ) -> dict:
        try:
            requested_start = int(start_line)
            requested_end = int(end_line)
            context = int(context_lines)
        except (TypeError, ValueError) as exc:
            raise ValueError("Line boundaries and context must be integers") from exc
        if requested_start < 1 or requested_end < requested_start:
            raise ValueError("Line range must satisfy 1 <= start_line <= end_line")
        if requested_end - requested_start + 1 > self.MAX_READ_LINES:
            raise ValueError(f"Requested range exceeds {self.MAX_READ_LINES} lines")
        if context < 0 or context > self.MAX_CONTEXT_LINES:
            raise ValueError(f"context_lines must be between 0 and {self.MAX_CONTEXT_LINES}")

        source = self.fs.read(path)
        lines = source.splitlines()
        total = len(lines)
        if requested_start > total and total > 0:
            raise ValueError(f"start_line {requested_start} exceeds file length {total}")
        actual_start = max(1, requested_start - context)
        actual_end = min(total, requested_end + context)
        excerpt = [
            {"line": number, "text": lines[number - 1]}
            for number in range(actual_start, actual_end + 1)
        ]
        return {
            "path": path,
            "requested_start": requested_start,
            "requested_end": requested_end,
            "actual_start": actual_start,
            "actual_end": actual_end,
            "total_lines": total,
            "context_lines": context,
            "lines": excerpt,
            "source": "\n".join(item["text"] for item in excerpt),
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
        return sorted(imports, key=lambda item: item["line"])

    def find_references(
        self,
        name: str,
        path: Optional[str] = None,
        limit: int = 200,
    ) -> List[dict]:
        if not name or not str(name).strip():
            raise ValueError("Reference name must not be empty")
        try:
            result_limit = int(limit)
        except (TypeError, ValueError) as exc:
            raise ValueError("Reference limit must be an integer") from exc
        if result_limit < 1 or result_limit > self.MAX_REFERENCE_RESULTS:
            raise ValueError(f"Reference limit must be between 1 and {self.MAX_REFERENCE_RESULTS}")

        refs: List[dict] = []
        for file_path in self._python_files(path):
            rel = self._relative(file_path)
            parsed = self._parse_for_scan(file_path)
            if parsed is None:
                continue
            source, tree = parsed
            source_lines = source.splitlines()
            for node in ast.walk(tree):
                reference = self._reference_entry(node, str(name), rel, source_lines)
                if reference:
                    refs.append(reference)
            if len(refs) >= result_limit:
                break
        return sorted(
            refs,
            key=lambda item: (item["path"], item["line"], item["column"], item["context"]),
        )[:result_limit]

    def find_routes(
        self,
        path: Optional[str] = None,
        route: Optional[str] = None,
        method: Optional[str] = None,
    ) -> List[dict]:
        route_filter = str(route).strip() if route is not None else None
        method_filter = str(method).strip().upper() if method else None
        matches: List[dict] = []

        for file_path in self._python_files(path):
            rel = self._relative(file_path)
            parsed = self._parse_for_scan(file_path)
            if parsed is None:
                continue
            source, tree = parsed
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for decorator in node.decorator_list:
                        entry = self._decorator_route_entry(decorator, node, rel)
                        if entry and self._route_matches(entry, route_filter, method_filter):
                            matches.append(entry)
                if isinstance(node, ast.Call):
                    entry = self._django_route_entry(node, rel)
                    if entry and self._route_matches(entry, route_filter, method_filter):
                        matches.append(entry)

        unique = {
            (
                item["path"],
                item["line_start"],
                item["route"],
                tuple(item["methods"]),
                item["handler"],
            ): item
            for item in matches
        }
        return sorted(
            unique.values(),
            key=lambda item: (item["path"], item["line_start"], item["route"]),
        )

    def explain_ambiguity(self, name: str, kind: Optional[str] = None) -> dict:
        matches = self.find_symbol(name, kind)
        return {
            "name": name,
            "kind": kind,
            "count": len(matches),
            "matches": matches,
            "ambiguous": len(matches) > 1,
        }

    def _python_files(self, path: Optional[str] = None) -> Iterable[Path]:
        if path:
            resolved = self.fs._validate_path(path)
            if not resolved.exists():
                raise ValueError(f"Path not found: {path}")
            candidates = [resolved] if resolved.is_file() else resolved.rglob("*.py")
        else:
            candidates = self.workspace_root.rglob("*.py")
        files = [
            candidate
            for candidate in candidates
            if candidate.is_file()
            and candidate.suffix == ".py"
            and not any(part in self.IGNORED_DIRECTORIES for part in candidate.relative_to(self.workspace_root).parts)
        ]
        return sorted(files)

    def _relative(self, path: Path) -> str:
        return str(path.resolve().relative_to(self.workspace_root))

    def _parse_for_scan(self, path: Path) -> Optional[tuple[str, ast.AST]]:
        try:
            source = self.fs.read(self._relative(path))
            return source, ast.parse(source)
        except (OSError, UnicodeError, SyntaxError, ValueError):
            return None

    def _reference_entry(
        self,
        node: ast.AST,
        name: str,
        path: str,
        source_lines: list[str],
    ) -> Optional[dict]:
        if isinstance(node, ast.Name) and node.id == name:
            context = type(node.ctx).__name__.lower()
            line = node.lineno
            column = node.col_offset
        elif isinstance(node, ast.Attribute) and node.attr == name:
            context = "attribute"
            line = node.lineno
            column = node.col_offset
        elif isinstance(node, ast.alias) and (node.name == name or node.asname == name):
            context = "import_alias"
            line = getattr(node, "lineno", 1)
            column = getattr(node, "col_offset", 0)
        else:
            return None
        source_line = source_lines[line - 1].strip() if 0 < line <= len(source_lines) else ""
        return {
            "path": path,
            "name": name,
            "line": line,
            "column": column,
            "context": context,
            "source_line": source_line,
        }

    def _decorator_route_entry(
        self,
        decorator: ast.AST,
        handler: ast.FunctionDef | ast.AsyncFunctionDef,
        path: str,
    ) -> Optional[dict]:
        if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
            return None
        verb = decorator.func.attr.lower()
        if verb not in self.HTTP_METHODS and verb != "route":
            return None
        route = self._literal_string(decorator.args[0]) if decorator.args else None
        if route is None:
            return None
        if verb == "route":
            methods = self._keyword_methods(decorator) or ["GET"]
            framework = "flask"
        else:
            methods = [verb.upper()]
            framework = "fastapi_or_flask"
        return {
            "path": path,
            "route": route,
            "methods": methods,
            "handler": handler.name,
            "framework": framework,
            "line_start": handler.lineno,
            "line_end": handler.end_lineno,
            "decorator_line": getattr(decorator, "lineno", handler.lineno),
            "is_async": isinstance(handler, ast.AsyncFunctionDef),
        }

    def _django_route_entry(self, node: ast.Call, path: str) -> Optional[dict]:
        function_name = self._call_name(node.func)
        if function_name not in {"path", "re_path"} or len(node.args) < 2:
            return None
        route = self._literal_string(node.args[0])
        if route is None:
            return None
        try:
            handler = ast.unparse(node.args[1])
        except Exception:
            handler = "unknown"
        return {
            "path": path,
            "route": route,
            "methods": ["ANY"],
            "handler": handler,
            "framework": "django",
            "line_start": node.lineno,
            "line_end": node.end_lineno,
            "decorator_line": None,
            "is_async": False,
            "route_kind": function_name,
        }

    @staticmethod
    def _route_matches(entry: dict, route: Optional[str], method: Optional[str]) -> bool:
        if route and route not in entry["route"]:
            return False
        if method and method not in entry["methods"] and "ANY" not in entry["methods"]:
            return False
        return True

    @staticmethod
    def _literal_string(node: ast.AST) -> Optional[str]:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.Str):
            return node.s
        return None

    @staticmethod
    def _keyword_methods(call: ast.Call) -> list[str]:
        keyword = next((item for item in call.keywords if item.arg == "methods"), None)
        if keyword is None:
            return []
        if isinstance(keyword.value, (ast.List, ast.Tuple, ast.Set)):
            methods = []
            for item in keyword.value.elts:
                value = CodeNavigationTool._literal_string(item)
                if value:
                    methods.append(value.upper())
            return methods
        return []

    @staticmethod
    def _call_name(node: ast.AST) -> Optional[str]:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        return None

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
