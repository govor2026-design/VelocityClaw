import json
from pathlib import Path
from typing import Any, Dict
import yaml


class EditorTool:
    def parse_json(self, text: str) -> Dict[str, Any]:
        return json.loads(text)

    def dump_json(self, data: Any, indent: int = 2) -> str:
        return json.dumps(data, indent=indent, ensure_ascii=False)

    def parse_yaml(self, text: str) -> Any:
        return yaml.safe_load(text)

    def dump_yaml(self, data: Any) -> str:
        return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)

    def read_markdown(self, path: str) -> str:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()

    def write_markdown(self, path: str, content: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)
