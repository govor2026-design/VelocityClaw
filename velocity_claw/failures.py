from __future__ import annotations

from enum import Enum


class ProviderNotConfiguredError(Exception):
    pass


class ProviderRequestError(Exception):
    pass


class ProviderResponseError(Exception):
    pass


class SecurityViolationError(ValueError):
    """Raised when an action violates agent security policy."""


class PlanningError(ValueError):
    pass


class UnknownToolError(ValueError):
    pass


class FailureType(str, Enum):
    """Stable machine-readable failure categories used across run boundaries."""

    POLICY_DENIED = "policy_denied"
    SECURITY_VIOLATION = "security_violation"
    PROVIDER_NOT_CONFIGURED = "provider_not_configured"
    PROVIDER_REQUEST_FAILED = "provider_request_failed"
    PROVIDER_RESPONSE_INVALID = "provider_response_invalid"
    PLANNING_FAILED = "planning_failed"
    TEST_FAILED = "test_failed"
    TOOL_NOT_FOUND = "tool_not_found"
    TOOL_INPUT_INVALID = "tool_input_invalid"
    TOOL_TIMEOUT = "tool_timeout"
    TOOL_EXECUTION_FAILED = "tool_execution_failed"
    INTERNAL_ERROR = "internal_error"


def classify_failure(
    exc: BaseException,
    *,
    phase: str | None = None,
    tool: str | None = None,
) -> str:
    """Classify an exception without coupling callers to its message text."""

    if isinstance(exc, ProviderNotConfiguredError):
        return FailureType.PROVIDER_NOT_CONFIGURED.value
    if isinstance(exc, ProviderRequestError):
        return FailureType.PROVIDER_REQUEST_FAILED.value
    if isinstance(exc, ProviderResponseError):
        return FailureType.PROVIDER_RESPONSE_INVALID.value
    if isinstance(exc, (SecurityViolationError, PermissionError)):
        return FailureType.SECURITY_VIOLATION.value
    if phase == "security":
        return FailureType.SECURITY_VIOLATION.value
    if isinstance(exc, PlanningError):
        return FailureType.PLANNING_FAILED.value
    if phase == "planning":
        return FailureType.PLANNING_FAILED.value
    if isinstance(exc, TimeoutError) or "timed out" in str(exc).lower():
        return FailureType.TOOL_TIMEOUT.value
    if isinstance(exc, UnknownToolError):
        return FailureType.TOOL_NOT_FOUND.value
    if isinstance(exc, ValueError):
        return FailureType.TOOL_INPUT_INVALID.value
    if tool:
        return FailureType.TOOL_EXECUTION_FAILED.value
    return FailureType.INTERNAL_ERROR.value
