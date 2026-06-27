import asyncio
import json
from types import SimpleNamespace
from unittest.mock import patch

from velocity_claw.api import errors


def test_unhandled_exception_handler_logs_supplied_traceback() -> None:
    request = SimpleNamespace(state=SimpleNamespace(request_id="request-123"))

    try:
        raise RuntimeError("boom")
    except RuntimeError as exc:
        expected_traceback = exc.__traceback__
        with patch.object(errors.LOGGER, "error") as log_error:
            response = asyncio.run(errors.unhandled_exception_handler(request, exc))

    log_error.assert_called_once_with(
        "Unhandled API exception request_id=%s",
        "request-123",
        exc_info=(RuntimeError, exc, expected_traceback),
    )
    assert response.status_code == 500
    assert json.loads(response.body) == {
        "status": "error",
        "error": {
            "code": "internal_error",
            "message": "Internal server error",
        },
        "request_id": "request-123",
    }
