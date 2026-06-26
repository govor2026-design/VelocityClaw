from __future__ import annotations

import difflib
from pathlib import Path
from typing import Any

from velocity_claw.config.settings import Settings
from velocity_claw.tools.fs import FileSystemTool


class FileDiffTool:
    """Preview and apply direct filesystem edits with a unified diff result."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.fs = FileSystemTool(settings)

    @staticmethod
    def _unified_diff(path: str, before: str, after: str) -> str:
        return "".join(
            difflib.unified_diff(
                before.splitlines(keepends=True),
                after.splitlines(keepends=True),
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
            )
        )

    def _read_existing(self, path: str) -> str:
        resolved = self.fs._validate_path(path)
        if not resolved.exists():
            return ""
        return self.fs.read(path)

    def prepare(self, action: str, path: str, **args: Any) -> dict[str, Any]:
        before = self._read_existing(path)
        if action == "fs.write":
            after = str(args.get("content", ""))
        elif action == "fs.append":
            after = before + str(args.get("content", ""))
        elif action == "fs.replace":
            old_string = str(args.get("old_string", ""))
            if old_string not in before:
                raise ValueError(f"Old string not found in {path}")
            after = before.replace(old_string, str(args.get("new_string", "")), 1)
        else:
            raise ValueError(f"Unsupported file action: {action}")

        encoded_size = len(after.encode("utf-8"))
        if encoded_size > self.settings.max_file_size:
            raise ValueError(f"Content too large: {encoded_size}")

        display_path = str(Path(path))
        return {
            "action": action,
            "path": display_path,
            "before": before,
            "after": after,
            "changed": before != after,
            "diff": self._unified_diff(display_path, before, after),
            "bytes_before": len(before.encode("utf-8")),
            "bytes_after": encoded_size,
        }

    def execute(self, action: str, path: str, *, preview_only: bool = False, **args: Any) -> dict[str, Any]:
        prepared = self.prepare(action, path, **args)
        if not preview_only and prepared["changed"]:
            self.fs.write(path, prepared["after"])
        return {
            "status": "simulated" if preview_only else "completed",
            "preview_only": preview_only,
            "action": action,
            "path": prepared["path"],
            "changed": prepared["changed"],
            "diff": prepared["diff"],
            "bytes_before": prepared["bytes_before"],
            "bytes_after": prepared["bytes_after"],
        }
