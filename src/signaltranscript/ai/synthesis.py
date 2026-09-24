"""Provider-neutral global synthesis over completed long-form section evidence.

A section result is never promoted to a global summary by concatenation.  This
module defines a separate synthesis call and validates that its evidence belongs
to the exact completed transcript.  Positional coverage is structural evidence,
not semantic or factual verification.
"""

from dataclasses import dataclass
from typing import Protocol

from signaltranscript.ai.coverage import PositionalCoverage, assess_reference_positions
from signaltranscript.ai.long_form import SectionedAnalysis
from signaltranscript.ai.ports import Analysis, Transcript, validate_analysis


class SynthesisValidationError(ValueError):
    """The inputs or output cannot support a global synthesis claim."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class GlobalSynthesisProvider(Protocol):
    async def synthesize(
        self, transcript: Transcript, sectioned: SectionedAnalysis,
    ) -> Analysis:
        """Produce one global analysis from the transcript and completed sections."""
        ...


@dataclass(frozen=True, slots=True)
class GlobalSynthesis:
    analysis: Analysis
    coverage: PositionalCoverage


async def synthesize_global(
    transcript: Transcript,
    sectioned: SectionedAnalysis,
    provider: GlobalSynthesisProvider,
    *,
    require_all_positions: bool = True,
) -> GlobalSynthesis:
    """Run one explicit synthesis call and validate its transcript evidence.

    There is no retry, fallback or provider selection here.  Incomplete section
    work is rejected before the provider is called.  The returned Analysis must
    reference only original transcript segments.  For transcripts with at least
    three segments, the default policy additionally requires references spanning
    beginning, middle and end before the result can be represented as global.
    """
    if not isinstance(transcript, Transcript):
        raise TypeError("transcript must be a canonical Transcript")
    if not isinstance(sectioned, SectionedAnalysis):
        raise TypeError("sectioned must be a SectionedAnalysis")
    if sectioned.video_id != transcript.video_id:
        raise SynthesisValidationError("VIDEO_ID_MISMATCH")
    if not sectioned.complete:
        raise SynthesisValidationError("SECTIONS_INCOMPLETE")

    section_ids = tuple(section.segment_ids for section in sectioned.sections)
    # Validate exact ordered section coverage before any potentially remote call.
    try:
        assess_reference_positions(transcript, section_ids, ())
    except ValueError as exc:
        raise SynthesisValidationError("SECTION_COVERAGE_MISMATCH") from exc

    analysis = await provider.synthesize(transcript, sectioned)
    try:
        validate_analysis(transcript, analysis)
    except (TypeError, ValueError) as exc:
        raise SynthesisValidationError("INVALID_SYNTHESIS") from exc

    references = (
        segment_id
        for idea in analysis.ideas
        for segment_id in idea.source_segment_ids
    )
    try:
        coverage = assess_reference_positions(transcript, section_ids, references)
    except ValueError as exc:
        raise SynthesisValidationError("INVALID_SYNTHESIS") from exc

    if require_all_positions and len(transcript.segments) >= 3 and not coverage.spans_all_positions:
        raise SynthesisValidationError("INSUFFICIENT_POSITIONAL_COVERAGE")
    return GlobalSynthesis(analysis=analysis, coverage=coverage)
