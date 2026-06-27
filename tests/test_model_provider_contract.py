import inspect

import pytest

from velocity_claw.models.providers import ModelProvider


def test_model_provider_is_abstract() -> None:
    assert inspect.isabstract(ModelProvider)

    with pytest.raises(TypeError):
        ModelProvider()
