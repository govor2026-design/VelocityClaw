from typing import get_type_hints

from velocity_claw.models.providers import ModelProvider


def test_model_provider_payload_annotations_are_parameterized() -> None:
    build_hints = get_type_hints(ModelProvider.build_payload)
    parse_hints = get_type_hints(ModelProvider.parse_response)

    assert build_hints["return"] == dict[str, object]
    assert parse_hints["payload"] == dict[str, object]
