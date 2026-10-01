"""Offline contracts for explicit global synthesis."""

import unittest

from signaltranscript.ai.errors import ProviderFailure
from signaltranscript.ai.long_form import AnalyzedSection, SectionedAnalysis
from signaltranscript.ai.ports import Analysis, Idea, Segment, Transcript
from signaltranscript.ai.synthesis import SynthesisValidationError, synthesize_global


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


def section(index: int, ids: tuple[str, ...]) -> AnalyzedSection:
    return AnalyzedSection(
        index=index,
        segment_ids=ids,
        analysis=Analysis(
            summary=f"Resumo de seção {index}",
            ideas=(Idea(f"Tema {index}", "Evidência local", (ids[0],)),),
            provider="section-fake",
            model="section-model",
        ),
    )


def complete() -> SectionedAnalysis:
    return SectionedAnalysis(
        "video-one",
        3,
        (
            section(0, ("s0", "s1", "s2")),
            section(1, ("s3", "s4", "s5")),
            section(2, ("s6", "s7", "s8")),
        ),
    )


class FakeSynthesisProvider:
    def __init__(self, analysis: Analysis) -> None:
        self.analysis = analysis
        self.calls = 0

    async def synthesize(self, transcript, sectioned):
        self.calls += 1
        return self.analysis


def synthesis(refs: tuple[str, ...]) -> Analysis:
    return Analysis(
        summary="Síntese global explícita.",
        ideas=(Idea("Tema global", "Explicação global", refs),),
        provider="synthesis-fake",
        model="synthesis-model",
    )


class GlobalSynthesisTests(unittest.IsolatedAsyncioTestCase):
    async def test_accepts_explicit_global_result_with_beginning_middle_end_evidence(self):
        provider = FakeSynthesisProvider(synthesis(("s0", "s4", "s8")))
        result = await synthesize_global(transcript(), complete(), provider)
        self.assertEqual(provider.calls, 1)
        self.assertEqual(result.analysis.summary, "Síntese global explícita.")
        self.assertTrue(result.coverage.spans_all_positions)
        self.assertEqual(result.coverage.referenced_segments, 3)

    async def test_incomplete_sections_fail_before_provider_call(self):
        provider = FakeSynthesisProvider(synthesis(("s0", "s4", "s8")))
        partial = SectionedAnalysis("video-one", 3, (section(0, ("s0", "s1", "s2")),), ProviderFailure("TIMEOUT"))
        with self.assertRaises(SynthesisValidationError) as caught:
            await synthesize_global(transcript(), partial, provider)
        self.assertEqual(caught.exception.code, "SECTIONS_INCOMPLETE")
        self.assertEqual(provider.calls, 0)

    async def test_mismatched_section_plan_fails_before_provider_call(self):
        provider = FakeSynthesisProvider(synthesis(("s0", "s4", "s8")))
        wrong = SectionedAnalysis("video-one", 1, (section(0, ("s0", "s2", "s1", "s3", "s4", "s5", "s6", "s7", "s8")),))
        with self.assertRaises(SynthesisValidationError) as caught:
            await synthesize_global(transcript(), wrong, provider)
        self.assertEqual(caught.exception.code, "SECTION_COVERAGE_MISMATCH")
        self.assertEqual(provider.calls, 0)

    async def test_foreign_reference_is_rejected(self):
        provider = FakeSynthesisProvider(synthesis(("s0", "foreign", "s8")))
        with self.assertRaises(SynthesisValidationError) as caught:
            await synthesize_global(transcript(), complete(), provider)
        self.assertEqual(caught.exception.code, "INVALID_SYNTHESIS")

    async def test_global_claim_requires_middle_reference(self):
        provider = FakeSynthesisProvider(synthesis(("s0", "s1", "s8")))
        with self.assertRaises(SynthesisValidationError) as caught:
            await synthesize_global(transcript(), complete(), provider)
        self.assertEqual(caught.exception.code, "INSUFFICIENT_POSITIONAL_COVERAGE")

    async def test_policy_can_measure_without_promoting_full_coverage(self):
        provider = FakeSynthesisProvider(synthesis(("s0", "s8")))
        result = await synthesize_global(
            transcript(), complete(), provider, require_all_positions=False,
        )
        self.assertFalse(result.coverage.spans_all_positions)

    async def test_short_transcript_does_not_require_impossible_three_buckets(self):
        source = transcript(2)
        parts = SectionedAnalysis("video-one", 1, (section(0, ("s0", "s1")),))
        provider = FakeSynthesisProvider(synthesis(("s0", "s1")))
        result = await synthesize_global(source, parts, provider)
        self.assertFalse(result.coverage.spans_all_positions)


if __name__ == "__main__":
    unittest.main()
