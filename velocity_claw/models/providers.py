class ModelProvider:
    def build_payload(self, prompt: str, task_type: str) -> dict[str, object]:
        raise NotImplementedError()

    def parse_response(self, payload: dict[str, object]) -> str:
        raise NotImplementedError()
