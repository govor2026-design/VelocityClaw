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

    def _validate_path(self, path: str) -> Path:
        """Validate and resolve path within workspace."""
        raw = Path(path)
        candidate = raw if raw.is_absolute() else (self.workspace_root / raw)
        try:
            resolved = candidate.resolve()
        except (OSError, ValueError) as e:
            raise ValueError(f"Invalid path: {e}")

        if not resolved.is_relative_to(self.workspace_root):
            raise ValueError(f"Path outside workspace: {resolved}")

        return resolved

    def _check_file_size(self, path: Path) -> None:
        if path.exists() and path.stat().st_size > self.settings.max_file_size:
            raise ValueError(f"File too large: {path.stat().st_size} > {self.settings.max_file_size}")

    def read(self, path: str) -> str:
        resolved = self._validate_path(path)
        self._check_file_size(resolved)
        try:
            with open(resolved, "r", encoding="utf-8") as handle:
                content = handle.read()
                if len(content.encode("utf-8")) > self.settings.max_file_size:
                    raise ValueError(f"Content too large: {len(content)}")
                return content
        except UnicodeDecodeError:
            raise ValueError(f"Binary file detected: {resolved}")

    def write(self, path: str, content: str) -> None:
        resolved = self._validate_path(path)
        if len(content.encode("utf-8")) > self.settings.max_file_size:
            raise ValueError(f"Content too large: {len(content)}")
        resolved.parent.mkdir(parents=True, exist_ok=True)
        with open(resolved, "w", encoding="utf-8") as handle:
            handle.write(content)

    def append(self, path: str, content: str) -> None:
        resolved = self._validate_path(path)
        current_size = resolved.stat().st_size if resolved.exists() else 0
        if current_size + len(content.encode("utf-8")) > self.settings.max_file_size:
            raise ValueError("File would exceed size limit")
        resolved.parent.mkdir(parents=True, exist_ok=True)
        with open(resolved, "a", encoding="utf-8") as handle:
            handle.write(content)

    def replace(self, path: str, old_string: str, new_string: str) -> None:
        content = self.read(path)
        if old_string not in content:
            raise ValueError(f"Old string not found in {path}")
        self.write(path, content.replace(old_string, new_string, 1))

    def exists(self, path: str) -> bool:
        return self._validate_path(path).exists()

    def search(self, root: str, pattern: str, extensions: Optional[List[str]] = None) -> List[str]:
        root_resolved = self._validate_path(root)
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
        resolved = self._validate_path(path)
        if not resolved.is_dir():
            raise ValueError(f"Not a directory: {resolved}")
        return [str(p.relative_to(self.workspace_root)) for p in resolved.iterdir()]

    def to_json(self, path: str):
        try:
            return json.loads(self.read(path))
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")

    def write_json(self, path: str, data):
        json_str = json.dumps(data, indent=2, ensure_ascii=False)
        if len(json_str.encode("utf-8")) > self.settings.max_file_size:
            raise ValueError("JSON too large")
        self.write(path, json_str)
