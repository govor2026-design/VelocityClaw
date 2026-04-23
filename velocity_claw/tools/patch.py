from __future__ import annotations

import ast
import difflib
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from velocity_claw.config.settings import Settings
from velocity_claw.tools.fs import FileSystemTool


class PatchError(ValueError):
    pass


@dataclass
class PatchResult:
    op: str
    path: str
    changed: bool
    diff: str
    preview_only: bool
    details: dict

    def to_dict(self) -> dict:
        return {
            "op": self.op,
            "path": self.path,
            "changed": self.changed,
            "diff": self.diff,
            "preview_only": self.preview_only,
            "details": self.details,
        }


class PatchEngine:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.fs = FileSystemTool(settings)
        self.workspace_root = Path(settings.workspace_root).resolve()

    def preview(self, patch: dict) -> dict:
        return self._apply_or_preview(patch, preview_only=True).to_dict()

    def apply(self, patch: dict, *, dry_run: bool = False) -> dict:
        return self._apply_or_preview(patch, preview_only=dry_run).to_dict()

    def _apply_or_preview(self, patch: dict, *, preview_only: bool) -> PatchResult:
        op = patch.get("op")
        path = patch.get("path")
        if not op or not path:
            raise PatchError("Patch must include op and path")

        resolved = self.fs._validate_path(path)
        details = {"resolved_path": str(resolved)}
        try:
            original = self.fs.read(path) if resolved.exists() else ""
        except ValueError as e:
            message = str(e)
            if "Binary file detected" in message:
                raise PatchError("binary file")
            if "File too large" in message or "Content too large" in message:
                raise PatchError("file too large")
            raise PatchError(message)

        updated, patch_details = self._execute_patch(op, original, patch)
        details.update(patch_details)
        changed = updated != original
        diff = self._make_diff(str(Path(path)), original, updated)

        if not preview_only and changed:
            try:
                self.fs.write(path, updated)
            except ValueError as e:
                message = str(e)
                if "Content too large" in message or "File too large" in message:
                    raise PatchError("file too large")
                raise PatchError(message)

        return PatchResult(
            op=op,
            path=str(Path(path)),
            changed=changed,
            diff=diff,
            preview_only=preview_only,
            details=details,
        )

    def _execute_patch(self, op: str, content: str, patch: dict) -> tuple[str, dict]:
        if op == "insert":
            anchor = patch.get("anchor")
            new_text = patch.get("content", "")
            if anchor is None:
                raise PatchError("insert requires anchor")
            count = content.count(anchor)
            if count == 0:
                raise PatchError("anchor not found")
            if count > 1:
                raise PatchError("ambiguous anchor match")
            position = patch.get("position", "after")
            idx = content.find(anchor)
            if position == "before":
                return content[:idx] + new_text + content[idx:], {"anchor_matches": count, "position": position}
            idx += len(anchor)
            return content[:idx] + new_text + content[idx:], {"anchor_matches": count, "position": position}
        if op == "replace_block":
            target = patch.get("target")
            replacement = patch.get("replacement")
            if not target:
                raise PatchError("replace_block requires target")
            if replacement is None:
                raise PatchError("replace_block requires replacement")
            count = content.count(target)
            if count == 0:
                raise PatchError("target block not found")
            if count > 1:
                raise PatchError("ambiguous target block match")
            return content.replace(target, replacement, 1), {"target_matches": count}
        if op == "append":
            new_text = patch.get("content", "")
            return content + new_text, {"appended_bytes": len(new_text.encode("utf-8"))}
        if op == "replace_function":
            updated = self._replace_symbol_block(content, patch.get("name"), "function", patch.get("replacement"))
            return updated, {"symbol_kind": "function", "symbol_name": patch.get("name")}
        if op == "replace_class":
            updated = self._replace_symbol_block(content, patch.get("name"), "class", patch.get("replacement"))
            return updated, {"symbol_kind": "class", "symbol_name": patch.get("name")}
        raise PatchError(f"Unsupported patch op: {op}")

    def _replace_symbol_block(self, content: str, name: Optional[str], kind: str, replacement: Optional[str]) -> str:
        if not name:
            raise PatchError(f"replace_{kind} requires name")
        if replacement is None:
            raise PatchError(f"replace_{kind} requires replacement")
        lines = content.splitlines(keepends=True)
        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            raise PatchError(f"failed to parse file for symbol replacement: {e}")

        matches = []
        for node in ast.walk(tree):
            if kind == "function" and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
                matches.append(node)
            elif kind == "class" and isinstance(node, ast.ClassDef) and node.name == name:
                matches.append(node)
        if not matches:
            raise PatchError(f"{kind} '{name}' not found")
        if len(matches) > 1:
            raise PatchError(f"ambiguous {kind} match for '{name}'")
        node = matches[0]
        start = node.lineno - 1
        end = node.end_lineno
        replacement_text = replacement if replacement.endswith("\n") else replacement + "\n"
        new_lines = lines[:start] + [replacement_text] + lines[end:]
        return "".join(new_lines)

    def _make_diff(self, path: str, original: str, updated: str) -> str:
        return "".join(
            difflib.unified_diff(
                original.splitlines(keepends=True),
                updated.splitlines(keepends=True),
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
            )
        )
