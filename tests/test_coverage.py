"""Offline contracts for deterministic positional coverage evidence."""

import unittest

from signaltranscript.ai.coverage import (
    CoverageValidationError,
    assess_positional_coverage,
)
from signaltranscript.ai.long_form import AnalyzedSection, SectionedAnalysis
from signaltranscript.ai.ports import Analysis, Idea, Segment, Transcript


def transcript(count: int = 9) -> Transcript:
    return Transcript(
        video_id="video-one",
        source="manual_import",
        language="pt-BR",
        segments=tuple(
            Segment(f"s{i}", f"segmento {i}", i * 1000, (i + 1) * 1000)
            for i in range(count)
        ),
    )


def section(index: int, ids: tuple[str, ...], refs: tuple[str, ...]) -> AnalyzedSection:
    return AnalyzedSection(
        index=index,
        segment_ids=ids,
        analysis=Analysis(
            summary=f"Resumo {index}",
            ideas=(Idea(f"Tema {index}", "Explicação", refs),),
            provider="fake",
            model="model-one",
        ),
    )


def complete_analysis(parts: tuple[AnalyzedSection, ...]) -> SectionedAnalysis:
    return SectionedAnalysis("video-one", len(parts), parts)


class PositionalCoverageTests(unittest.TestCase):
    def test_reports_beginning_middle_and_end_reference_coverage(self):
        source = transcript()
        result = complete_analysis((
            section(0, ("s0", "s1", "s2"), ("s0",)),
            section(1, ("s3", "s4", "s5"), ("s4",)),
            section(2, ("s6", "s7", "s8"), ("s8",)),
        ))

        coverage = assess_positional_coverage(source, result)

        self.assertEqual(coverage.total_segments, 9)
        self.assertEqual(coverage.referenced_segments, 3)
        self.assertTrue(coverage.beginning_referenced)
        self.assertTrue(coverage.middle_referenced)
        self.assertTrue(coverage.end_referenced)
        self.assertTrue(coverage.spans_all_positions)

    def test_missing_middle_is_explicit_not_promoted_to_full_coverage(self):
        source = transcript()
        result = complete_analysis((
            section(0, ("s0", "s1", "s2"), ("s1",)),
            section(1, ("s3", "s4", "s5"), ("s1",)),
            section(2, ("s6", "s7", "s8"), ("s7",)),
        ))

        coverage = assess_positional_coverage(source, result)

        self.assertTrue(coverage.beginning_referenced)
        self.assertFalse(coverage.middle_referenced)
        self.assertTrue(coverage.end_referenced)
        self.assertFalse(coverage.spans_all_positions)

    def test_duplicate_references_count_once(self):
        source = transcript()
        result = complete_analysis((
            section(0, ("s0", "s1", "s2"), ("s0", "s0")),
            section(1, ("s3", "s4", "s5"), ("s0",)),
            section(2, ("s6", "s7", "s8"), ("s0",)),
        ))
        self.assertEqual(assess_positional_coverage(source, result).referenced_segments, 1)

    def test_incomplete_analysis_is_not_coverage_evidence(self):
        source = transcript()
        result = SectionedAnalysis(
            "video-one",
            3,
            (section(0, ("s0", "s1", "s2"), ("s0",)),),
        )
        with self.assertRaises(CoverageValidationError) as caught:
            assess_positional_coverage(source, result)
        self.assertEqual(caught.exception.code, "ANALYSIS_INCOMPLETE")

    def test_section_plan_must_cover_exact_transcript_order(self):
        source = transcript(3)
        result = complete_analysis((section(0, ("s0", "s2", "s1"), ("s0",)),))
        with self.assertRaises(CoverageValidationError) as caught:
            assess_positional_coverage(source, result)
        self.assertEqual(caught.exception.code, "SECTION_COVERAGE_MISMATCH")

    def test_video_identity_must_match(self):
        source = transcript(3)
        result = SectionedAnalysis(
            "other-video",
            1,
            (section(0, ("s0", "s1", "s2"), ("s0",)),),
        )
        with self.assertRaises(CoverageValidationError) as caught:
            assess_positional_coverage(source, result)
        self.assertEqual(caught.exception.code, "VIDEO_ID_MISMATCH")

    def test_unknown_reference_is_rejected_even_if_constructed_outside_analyzer(self):
        source = transcript(3)
        result = complete_analysis((section(0, ("s0", "s1", "s2"), ("foreign",)),))
        with self.assertRaises(CoverageValidationError) as caught:
            assess_positional_coverage(source, result)
        self.assertEqual(caught.exception.code, "UNKNOWN_REFERENCE")

    def test_short_transcript_does_not_fake_all_three_positions(self):
        source = transcript(2)
        result = complete_analysis((section(0, ("s0", "s1"), ("s0", "s1")),))
        coverage = assess_positional_coverage(source, result)
        self.assertFalse(coverage.spans_all_positions)


if __name__ == "__main__":
    unittest.main()
