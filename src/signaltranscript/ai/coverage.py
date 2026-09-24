"""Deterministic coverage evidence for completed section-level analyses.

This module does not create a global summary and does not judge semantic truth.
It only proves whether analysis ideas reference real transcript segments across
coarse beginning/middle/end positions of the exact completed transcript.
"""

from dataclasses import dataclass

from signaltranscript.ai.long_form import SectionedAnalysis
from signaltranscript.ai.ports import Transcript


class CoverageValidationError(ValueError):
    """The analysis cannot be used as trustworthy positional coverage evidence."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class PositionalCoverage:
    """Reference coverage only; never semantic or factual verification."""

    total_segments: int
    referenced_segments: int
    beginning_referenced: bool
    middle_referenced: bool
    end_referenced: bool

    @property
    def spans_all_positions(self) -> bool:
        return self.beginning_referenced and self.middle_referenced and self.end_referenced


def _position(index: int, total: int) -> str:
    """Assign every segment deterministically to one of three ordered buckets."""
    # Multiplication avoids floating-point boundaries. For one/two-segment
    # transcripts not every bucket can exist, so spans_all_positions stays false.
    bucket = (index * 3) // total
    if bucket == 0:
        return "beginning"
    if bucket == 1:
        return "middle"
    return "end"


def assess_positional_coverage(
    transcript: Transcript,
    analysis: SectionedAnalysis,
) -> PositionalCoverage:
    """Validate exact section coverage, then measure idea-reference positions.

    Fail closed unless the section result is complete and its flattened segment
    IDs exactly equal the canonical transcript. References are already validated
    by the section analyzer; this function validates them again against the exact
    transcript before using them as evidence.
    """
    if not isinstance(transcript, Transcript):
        raise TypeError("transcript must be a canonical Transcript")
    if not isinstance(analysis, SectionedAnalysis):
        raise TypeError("analysis must be a SectionedAnalysis")
    if analysis.video_id != transcript.video_id:
        raise CoverageValidationError("VIDEO_ID_MISMATCH")
    if not analysis.complete:
        raise CoverageValidationError("ANALYSIS_INCOMPLETE")

    transcript_ids = tuple(segment.id for segment in transcript.segments)
    section_ids = tuple(
        segment_id
        for section in analysis.sections
        for segment_id in section.segment_ids
    )
    if section_ids != transcript_ids:
        raise CoverageValidationError("SECTION_COVERAGE_MISMATCH")
    if not transcript_ids:
        raise CoverageValidationError("EMPTY_TRANSCRIPT")

    index_by_id = {segment_id: index for index, segment_id in enumerate(transcript_ids)}
    referenced: set[str] = set()
    positions: set[str] = set()
    for section in analysis.sections:
        for idea in section.analysis.ideas:
            for segment_id in idea.source_segment_ids:
                index = index_by_id.get(segment_id)
                if index is None:
                    raise CoverageValidationError("UNKNOWN_REFERENCE")
                referenced.add(segment_id)
                positions.add(_position(index, len(transcript_ids)))

    return PositionalCoverage(
        total_segments=len(transcript_ids),
        referenced_segments=len(referenced),
        beginning_referenced="beginning" in positions,
        middle_referenced="middle" in positions,
        end_referenced="end" in positions,
    )
