"""Groq-specific transport classification shared by its independent adapters.

Never include exception strings, server response bodies or credentials in errors.
Scheduling a retry is exclusively the worker's responsibility.
"""

from collections.abc import Mapping
from math import isfinite

from signaltranscript.ai.errors import ProviderFailure


def retry_after(headers: object) -> float | None:
    if not isinstance(headers, Mapping):
        return None
    raw = headers.get("retry-after")
    try:
        seconds = float(raw)
    except (TypeError, ValueError, OverflowError):
        return None
    return seconds if isfinite(seconds) and 0 <= seconds <= 604_800 else None


def classify_sdk_error(exc: Exception) -> ProviderFailure | None:
    status = getattr(exc, "status_code", None)
    if type(status) is int:
        response = getattr(exc, "response", None)
        headers = getattr(response, "headers", None)
        if status == 429:
            return ProviderFailure("RATE_LIMITED", retryable=True,
                                   retry_after_seconds=retry_after(headers), status_code=status)
        if status in (401, 403):
            return ProviderFailure("ACCESS_DENIED", status_code=status)
        if status in (400, 413, 422):
            return ProviderFailure("INVALID_REQUEST", status_code=status)
        if status == 404:
            return ProviderFailure("MODEL_UNAVAILABLE", status_code=status)
        if status in (408, 409) or 500 <= status <= 599:
            return ProviderFailure("REMOTE_UNAVAILABLE", retryable=True,
                                   remote_outcome_unknown=True, status_code=status)
        return ProviderFailure("REMOTE_ERROR", status_code=status)

    try:
        from groq import APIConnectionError
    except ImportError:
        sdk_connection_error: type[Exception] | tuple[()] = ()
    else:
        sdk_connection_error = APIConnectionError
    if isinstance(exc, (ConnectionError, TimeoutError, sdk_connection_error)):
        return ProviderFailure("REMOTE_OUTCOME_UNKNOWN", retryable=True,
                               remote_outcome_unknown=True)
    return None
