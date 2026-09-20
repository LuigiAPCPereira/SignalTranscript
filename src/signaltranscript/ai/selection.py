"""Explicit composition boundary; never silently switch service or billing."""

from collections.abc import Mapping
from dataclasses import dataclass

from .ports import AnalysisProvider, TranscriptionProvider


@dataclass(frozen=True, slots=True)
class ProviderSelection:
    transcription: str
    analysis: str


@dataclass(frozen=True, slots=True)
class SelectedProviders:
    transcription: TranscriptionProvider
    analysis: AnalysisProvider


def select_providers(
    selection: ProviderSelection,
    *,
    transcribers: Mapping[str, TranscriptionProvider],
    analyzers: Mapping[str, AnalysisProvider],
) -> SelectedProviders:
    """Select independently from adapters assembled by the application root.

    Unknown/unconfigured provider names fail before any provider call. Callers
    must explicitly request a change; there is no implicit remote fallback.
    """
    if selection.transcription not in transcribers:
        raise ValueError(f"unconfigured transcription provider: {selection.transcription!r}")
    if selection.analysis not in analyzers:
        raise ValueError(f"unconfigured analysis provider: {selection.analysis!r}")
    return SelectedProviders(
        transcription=transcribers[selection.transcription],
        analysis=analyzers[selection.analysis],
    )
