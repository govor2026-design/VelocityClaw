import difflib
import json
import os
import re
from pathlib import Path
from typing import List, Optional

from velocity_claw.config.settings import Settings


class FileSystemTool:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.workspace_root = Path(settings.workspace_root).resolve()

    def validate_path(self, path: str) -> Path:
        """Validate and resolve a path within the configured workspace."""
        raw = Path(path)
        candidate = raw if raw.is_absolute() else (self.workspace_root / raw)
        try:
            resolved = candidate.resolve()
        except (OSError, ValueError) as exc:
            raise ValueError(f"Invalid path: {exc}") from exc

        if not resolved.is_relative_to(self.workspace_root):
            raise ValueError(f"Path outside workspace: {resolved}")
        return resolved

    def _validate_path(self, path: str) -> Path:
        """Backward-compatible alias; use validate_path in new code."""
        return self.validate_path(path)

    def _check_file_size(self, path: Path) -> None:
        if path.exists() and path.stat().st_size > self.settings.max_file_size:
            raise ValueError(f"File too large: {path.stat().st_size} > {self.settings.max_file_size}")

    def read_existing(self, resolved: Path) -> str:
        """Read a validated path, returning an empty string when it does not exist."""
        if not resolved.exists():
            return ""
        self._check_file_size(resolved)
        try:
            with open(resolved, "r", encoding="utf-8") as handle:
                return handle.read()
        except UnicodeDecodeError as exc:
            raise ValueError(f"Binary file detected: {resolved}") from exc

    def _read_existing(self, resolved: Path) -> str:
        """Backward-compatible alias; use read_existing in new code."""
        return self.read_existing(resolved)

    def display_path(self, resolved: Path) -> str:
        """Return a workspace-relative path when possible."""
        try:
            return str(resolved.relative_to(self.workspace_root))
        except ValueError:
            return str(resolved)

    def _display_path(self, resolved: Path) -> str:
        """Backward-compatible alias; use display_path in new code."""
        return self.display_path(resolved)

    @staticmethod
    def make_diff(path: str, before: str, after: str) -> str:
        """Create a unified diff for a prospective file change."""
        return "".join(
            difflib.unified_diff(
                before.splitlines(keepends=True),
                after.splitlines(keepends=True),
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
            )
        )

    @staticmethod
    def _make_diff(path: str, before: str, after: str) -> str:
        """Backward-compatible alias; use make_diff in new code."""
        return FileSystemTool.make_diff(path, before, after)

    def _write_with_diff(self, path: str, before: str, after: str, action: str) -> dict:
        resolved = self.validate_path(path)
        encoded_size = len(after.encode("utf-8"))
        if encoded_size > self.settings.max_file_size:
            raise ValueError(f"Content too large: {encoded_size}")
        display_path = self.display_path(resolved)
        diff = self.make_diff(display_path, before, after)
        changed = before != after
        if changed:
            resolved.parent.mkdir(parents=True, exist_ok=True)
            with open(resolved, "w", encoding="utf-8") as handle:
                handle.write(after)
        return {
            "status": "completed",
            "action": action,
            "path": display_path,
            "changed": changed,
            "diff": diff,
            "bytes_before": len(before.encode("utf-8")),
            "bytes_after": encoded_size,
        }

    def read(self, path: str) -> str:
        resolved = self.validate_path(path)
        self._check_file_size(resolved)
        try:
            with open(resolved, "r", encoding="utf-8") as handle:
                content = handle.read()
                if len(content.encode("utf-8")) > self.settings.max_file_size:
                    raise ValueError(f"Content too large: {len(content)}")
                return content
        except UnicodeDecodeError as exc:
            raise ValueError(f"Binary file detected: {resolved}") from exc

    def write(self, path: str, content: str) -> dict:
        resolved = self.validate_path(path)
        before = self.read_existing(resolved)
        return self._write_with_diff(path, before, content, "fs.write")

    def append(self, path: str, content: str) -> dict:
        resolved = self.validate_path(path)
        before = self.read_existing(resolved)
        return self._write_with_diff(path, before, before + content, "fs.append")

    def replace(self, path: str, old_string: str, new_string: str) -> dict:
        resolved = self.validate_path(path)
        before = self.read_existing(resolved)
        if old_string not in before:
            raise ValueError(f"Old string not found in {path}")
        after = before.replace(old_string, new_string, 1)
        return self._write_with_diff(path, before, after, "fs.replace")

    def exists(self, path: str) -> bool:
        return self.validate_path(path).exists()

    def search(self, root: str, pattern: str, extensions: Optional[List[str]] = None) -> List[str]:
        root_resolved = self.validate_path(root)
        matches = []
        for base, _, files in os.walk(root_resolved):
            for name in files:
                if extensions and not any(name.endswith(ext) for ext in extensions):
                    continue
                path = Path(base) / name
                try:
                    self._check_file_size(path)
                    with open(path, "r", encoding="utf-8", errors="ignore") as handle:
                        text = handle.read()
                    if re.search(pattern, text, re.IGNORECASE):
                        matches.append(str(path.relative_to(self.workspace_root)))
                except (OSError, UnicodeDecodeError, ValueError):
                    continue
        return matches

    def list_dir(self, path: str) -> List[str]:
        resolved = self.validate_path(path)
        if not resolved.is_dir():
            raise ValueError(f"Not a directory: {resolved}")
        return [str(item.relative_to(self.workspace_root)) for item in resolved.iterdir()]

    def to_json(self, path: str):
        try:
            return json.loads(self.read(path))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON: {exc}") from exc

    def write_json(self, path: str, data):
        json_str = json.dumps(data, indent=2, ensure_ascii=False)
        if len(json_str.encode("utf-8")) > self.settings.max_file_size:
            raise ValueError("JSON too large")
        return self.write(path, json_str)
