from abc import ABC, abstractmethod


class ModelProvider(ABC):
    @abstractmethod
    def build_payload(self, prompt: str, task_type: str) -> dict[str, object]:
        raise NotImplementedError

    @abstractmethod
    def parse_response(self, payload: dict[str, object]) -> str:
        raise NotImplementedError
