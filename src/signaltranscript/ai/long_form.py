"""Provider-neutral, bounded, section-level analysis of long transcripts.

This is deliberately NOT a global-summary generator or a persistence worker.
Every planned section uses complete original segments and their original IDs.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import json

from signaltranscript.ai.errors import ProviderFailure
from signaltranscript.ai.ports import (
    Analysis, AnalysisProvider, Idea, Segment, Transcript, validate_analysis,
)


class ChunkPlanningError(ValueError):
    """Safe planning failure; no remote calls have been made when raised."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def compact_source_chars(transcript: Transcript) -> int:
    """Size of the compact text/ID envelope used by the initial Groq adapter.

    This counts Unicode code points, NOT tokens, request overhead or API quota.
    Other adapters may supply their own measurement function to the planner.
    """
    return len(json.dumps({
        "language": transcript.language,
        "segments": [{"id": seg.id, "text": seg.text} for seg in transcript.segments],
    }, ensure_ascii=False, separators=(",", ":")))


def _part(original: Transcript, segments: tuple[Segment, ...]) -> Transcript:
    return Transcript(
        video_id=original.video_id, source=original.source, segments=segments,
        language=original.language, provider=original.provider, model=original.model,
    )


def plan_sections(
    transcript: Transcript, *, max_chars: int,
    measure: Callable[[Transcript], int] = compact_source_chars,
    max_sections: int = 64,
) -> tuple[Transcript, ...]:
    """Preflight all contiguous sections; never split or silently drop a segment.

    No overlap in this first slice. The caller must supply a limit/measurement
    appropriate to the selected provider; character sizes do not bound tokens.
    """
    if not isinstance(transcript, Transcript):
        raise TypeError("transcript must be a canonical Transcript")
    if type(max_chars) is not int or max_chars <= 0:
        raise ValueError("max_chars must be a positive integer")
    if type(max_sections) is not int or max_sections <= 0:
        raise ValueError("max_sections must be a positive integer")

    def checked_size(segments: tuple[Segment, ...]) -> int:
        value = measure(_part(transcript, segments))
        if type(value) is not int or value < 0:
            raise ChunkPlanningError("INVALID_MEASUREMENT")
        return value

    sections: list[Transcript] = []
    current: tuple[Segment, ...] = ()
    for segment in transcript.segments:
        candidate = current + (segment,)
        if checked_size(candidate) <= max_chars:
            current = candidate
            continue
        if not current:
            raise ChunkPlanningError("SEGMENT_TOO_LARGE")
        sections.append(_part(transcript, current))
        if len(sections) >= max_sections:
            raise ChunkPlanningError("TOO_MANY_SECTIONS")
        current = (segment,)
        if checked_size(current) > max_chars:
            raise ChunkPlanningError("SEGMENT_TOO_LARGE")
    if current:
        sections.append(_part(transcript, current))
    if len(sections) > max_sections:
        raise ChunkPlanningError("TOO_MANY_SECTIONS")
    return tuple(sections)


@dataclass(frozen=True, slots=True)
class AnalyzedSection:
    index: int
    segment_ids: tuple[str, ...]
    analysis: Analysis


@dataclass(frozen=True, slots=True)
class SectionedAnalysis:
    """Section summaries are not a global summary; partial state is explicit."""
    video_id: str
    planned_sections: int
    sections: tuple[AnalyzedSection, ...]
    failure: ProviderFailure | None = None

    @property
    def complete(self) -> bool:
        return self.failure is None and len(self.sections) == self.planned_sections

    @property
    def section_summaries(self) -> tuple[str, ...]:
        return tuple(section.analysis.summary for section in self.sections)

    @property
    def collected_ideas(self) -> tuple[Idea, ...]:
        """Exact deduplication only; partial results remain partial if failure set."""
        seen: set[tuple[str, str, tuple[str, ...]]] = set()
        ideas: list[Idea] = []
        for section in self.sections:
            for idea in section.analysis.ideas:
                key = (idea.title, idea.explanation, idea.source_segment_ids)
                if key not in seen:
                    seen.add(key)
                    ideas.append(idea)
        return tuple(ideas)


async def analyze_in_sections(
    transcript: Transcript, provider: AnalysisProvider, *, max_chars: int,
    measure: Callable[[Transcript], int] = compact_source_chars,
    max_sections: int = 64,
    on_section_complete: Callable[[AnalyzedSection], Awaitable[None]] | None = None,
) -> SectionedAnalysis:
    """One selected provider, sequential calls, no implicit retry or fallback.

    Preflight is all-or-nothing. A known provider failure returns explicitly
    partial results; unexpected bugs and checkpoint failures propagate.
    """
    planned = plan_sections(
        transcript, max_chars=max_chars, measure=measure, max_sections=max_sections,
    )
    return await _analyze_planned(transcript.video_id, planned, provider,
                                  on_section_complete=on_section_complete)


async def _analyze_planned(
    video_id: str, planned: tuple[Transcript, ...], provider: AnalysisProvider, *,
    previous: tuple[AnalyzedSection, ...] = (),
    on_section_complete: Callable[[AnalyzedSection], Awaitable[None]] | None = None,
) -> SectionedAnalysis:
    """Execute an immutable plan, optionally starting after validated checkpoints."""
    if len(previous) > len(planned):
        raise ValueError("checkpoint contains too many sections")
    provider_identity: tuple[str, str] | None = None
    for index, analyzed in enumerate(previous):
        if analyzed.index != index or analyzed.segment_ids != tuple(seg.id for seg in planned[index].segments):
            raise ValueError("checkpoint does not match section plan")
        validate_analysis(planned[index], analyzed.analysis)
        identity = (analyzed.analysis.provider, analyzed.analysis.model)
        if provider_identity is not None and identity != provider_identity:
            raise ValueError("checkpoint mixes providers or models")
        provider_identity = identity
    completed: list[AnalyzedSection] = list(previous)
    for index in range(len(previous), len(planned)):
        section = planned[index]
        try:
            analysis = await provider.analyze(section)
        except ProviderFailure as failure:
            return SectionedAnalysis(video_id, len(planned), tuple(completed), failure)
        try:
            validate_analysis(section, analysis)
        except ValueError:
            return SectionedAnalysis(
                video_id, len(planned), tuple(completed),
                ProviderFailure("INVALID_RESPONSE"),
            )
        identity = (analysis.provider, analysis.model)
        if provider_identity is not None and provider_identity != identity:
            return SectionedAnalysis(
                video_id, len(planned), tuple(completed),
                ProviderFailure("PROVIDER_CHANGED"),
            )
        analyzed = AnalyzedSection(index, tuple(seg.id for seg in section.segments), analysis)
        if on_section_complete is not None:
            await on_section_complete(analyzed)
        completed.append(analyzed)
        provider_identity = identity
    return SectionedAnalysis(video_id, len(planned), tuple(completed))
