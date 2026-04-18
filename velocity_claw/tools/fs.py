import json
import os
import re
from pathlib import Path
from typing import List, Optional


class FileSystemTool:
    def read(self, path: str) -> str:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()

    def write(self, path: str, content: str) -> None:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)

    def exists(self, path: str) -> bool:
        return Path(path).exists()

    def search(self, root: str, pattern: str, extensions: Optional[List[str]] = None) -> List[str]:
        matches = []
        for base, _, files in os.walk(root):
            for name in files:
                if extensions and not any(name.endswith(ext) for ext in extensions):
                    continue
                path = os.path.join(base, name)
                try:
                    with open(path, "r", encoding="utf-8", errors="ignore") as handle:
                        text = handle.read()
                    if re.search(pattern, text, re.IGNORECASE):
                        matches.append(path)
                except OSError:
                    continue
        return matches

    def list_dir(self, path: str) -> List[str]:
        return [os.path.join(path, item) for item in os.listdir(path)]

    def to_json(self, path: str):
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def write_json(self, path: str, data):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
