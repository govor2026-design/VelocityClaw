from typing import Dict, Optional


class ModelProvider:
    def build_payload(self, prompt: str, task_type: str) -> Dict:
        raise NotImplementedError()

    def parse_response(self, payload: Dict) -> str:
        raise NotImplementedError()
