"""Errors shared across transcription and analysis providers, without SDK imports."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProviderFailure(Exception):
    """Safe, provider-neutral failure metadata for a future persistent worker."""

    code: str
    retryable: bool = False
    remote_outcome_unknown: bool = False
    retry_after_seconds: float | None = None
    status_code: int | None = None

    def __str__(self) -> str:
        return f"transcription provider failed: {self.code}"
