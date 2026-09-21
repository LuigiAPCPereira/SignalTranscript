"""Provider-neutral long-form tests; no network, SDK or credentials."""

import json
import unittest

from signaltranscript.ai.errors import ProviderFailure
from signaltranscript.ai.long_form import (
    ChunkPlanningError, analyze_in_sections, compact_source_chars, plan_sections,
)
from signaltranscript.ai.ports import Analysis, Idea, Segment, Transcript


def sample(count=5, *, width=70, timed=True):
    return Transcript(
        video_id="video-one", source="manual_caption", language="pt-BR",
        segments=tuple(
            Segment(f"s{i}", "á" * width, i * 1000 if timed else None,
                    (i + 1) * 1000 if timed else None) for i in range(count)
        ),
    )


class FakeProvider:
    def __init__(self, *, fail_at=None, bad_ref_at=None, switch_at=None):
        self.calls = []
        self.fail_at = fail_at
        self.bad_ref_at = bad_ref_at
        self.switch_at = switch_at

    async def analyze(self, transcript):
        number = len(self.calls)
        self.calls.append(transcript)
        if number == self.fail_at:
            raise ProviderFailure("RATE_LIMITED", retryable=True, retry_after_seconds=10)
        seg = transcript.segments[0]
        sid = "foreign" if number == self.bad_ref_at else seg.id
        model = "other-model" if number == self.switch_at else "model-one"
        return Analysis("Resumo do trecho", (Idea("Tema", "Explicação", (sid,)),), "fake", model)


class PlannerTests(unittest.TestCase):
    def test_one_small_section_is_identical_in_content(self):
        transcript = sample(3, timed=False)
        planned = plan_sections(transcript, max_chars=2000)
        self.assertEqual(len(planned), 1)
        self.assertEqual(planned[0], transcript)

    def test_splits_on_complete_segments_preserving_all_ids_order_times_and_text(self):
        transcript = sample(9)
        planned = plan_sections(transcript, max_chars=250)
        self.assertGreater(len(planned), 1)
        flattened = tuple(seg for part in planned for seg in part.segments)
        self.assertEqual(flattened, transcript.segments)
        self.assertTrue(all(compact_source_chars(part) <= 250 for part in planned))
        self.assertEqual({part.video_id for part in planned}, {"video-one"})
        self.assertEqual({part.language for part in planned}, {"pt-BR"})

    def test_source_size_matches_groq_adapter_envelope_exactly(self):
        transcript = sample(3)
        expected = json.dumps({
            "language": transcript.language,
            "segments": [{"id": seg.id, "text": seg.text} for seg in transcript.segments],
        }, ensure_ascii=False, separators=(",", ":"))
        self.assertEqual(compact_source_chars(transcript), len(expected))

    def test_oversize_single_segment_fails_without_truncation(self):
        transcript = sample(3, width=2000)
        with self.assertRaises(ChunkPlanningError) as caught:
            plan_sections(transcript, max_chars=250)
        self.assertEqual(caught.exception.code, "SEGMENT_TOO_LARGE")
        self.assertEqual(len(transcript.segments[0].text), 2000)

    def test_too_many_sections_fails_before_execution(self):
        with self.assertRaises(ChunkPlanningError) as caught:
            plan_sections(sample(20), max_chars=130, max_sections=2)
        self.assertEqual(caught.exception.code, "TOO_MANY_SECTIONS")

    def test_invalid_sizes_and_measurements_rejected(self):
        for size in (0, -1, True, 1.2):
            with self.subTest(size=size), self.assertRaises(ValueError):
                plan_sections(sample(1), max_chars=size)
        for measurement in (True, -5, "too many"):
            with self.subTest(measurement=measurement), self.assertRaises(ChunkPlanningError):
                plan_sections(sample(1), max_chars=300, measure=lambda _: measurement)

    def test_provider_specific_measurement_is_injected(self):
        transcript = sample(4)
        planned = plan_sections(transcript, max_chars=3, measure=lambda t: len(t.segments))
        self.assertEqual([len(part.segments) for part in planned], [3, 1])


class OrchestratorTests(unittest.IsolatedAsyncioTestCase):
    async def test_complete_coverage_and_sections_not_global_summary(self):
        transcript = sample(7)
        provider = FakeProvider()
        result = await analyze_in_sections(transcript, provider, max_chars=250)
        self.assertTrue(result.complete)
        self.assertIsNone(result.failure)
        self.assertEqual(len(result.sections), result.planned_sections)
        self.assertEqual(tuple(sid for part in result.sections for sid in part.segment_ids),
                         tuple(seg.id for seg in transcript.segments))
        self.assertEqual(len(result.section_summaries), result.planned_sections)
        self.assertFalse(hasattr(result, "summary"))
        self.assertEqual(len(result.collected_ideas), result.planned_sections)
        self.assertEqual([p.index for p in result.sections], list(range(result.planned_sections)))

    async def test_single_section_and_untimed_segments_supported(self):
        result = await analyze_in_sections(sample(2, timed=False), FakeProvider(), max_chars=1000)
        self.assertTrue(result.complete)
        self.assertEqual(result.sections[0].segment_ids, ("s0", "s1"))

    async def test_preflight_does_not_call_provider_on_late_oversize(self):
        transcript = Transcript("v", "import", (
            Segment("s0", "ok", None, None), Segment("s1", "x" * 3000, None, None)
        ))
        provider = FakeProvider()
        with self.assertRaises(ChunkPlanningError):
            await analyze_in_sections(transcript, provider, max_chars=250)
        self.assertEqual(provider.calls, [])

    async def test_partial_error_preserves_only_completed_sections(self):
        provider = FakeProvider(fail_at=1)
        result = await analyze_in_sections(sample(7), provider, max_chars=250)
        self.assertFalse(result.complete)
        self.assertEqual(result.failure.code, "RATE_LIMITED")
        self.assertEqual(result.failure.retry_after_seconds, 10)
        self.assertEqual(len(result.sections), 1)
        self.assertEqual(len(provider.calls), 2)
        self.assertEqual(len(result.collected_ideas), 1)

    async def test_unknown_reference_rejected_and_never_claims_success(self):
        result = await analyze_in_sections(sample(6), FakeProvider(bad_ref_at=1), max_chars=250)
        self.assertFalse(result.complete)
        self.assertEqual(result.failure.code, "INVALID_RESPONSE")
        self.assertEqual(len(result.sections), 1)

    async def test_provider_identity_change_detected(self):
        result = await analyze_in_sections(sample(6), FakeProvider(switch_at=1), max_chars=250)
        self.assertFalse(result.complete)
        self.assertEqual(result.failure.code, "PROVIDER_CHANGED")
        self.assertEqual(len(result.sections), 1)

    async def test_callbacks_order_and_completed_segments(self):
        persisted = []
        async def checkpoint(part):
            persisted.append((part.index, part.segment_ids))
        result = await analyze_in_sections(sample(7), FakeProvider(), max_chars=250,
                                           on_section_complete=checkpoint)
        self.assertTrue(result.complete)
        self.assertEqual(persisted, [(p.index, p.segment_ids) for p in result.sections])

    async def test_checkpoint_failure_is_not_masked_as_provider_failure(self):
        async def checkpoint(_):
            raise OSError("storage error")
        with self.assertRaisesRegex(OSError, "storage error"):
            await analyze_in_sections(sample(2), FakeProvider(), max_chars=1000,
                                      on_section_complete=checkpoint)

    async def test_programming_error_is_not_disguised(self):
        class Broken:
            async def analyze(self, transcript):
                raise AssertionError("bug")
        with self.assertRaisesRegex(AssertionError, "bug"):
            await analyze_in_sections(sample(2), Broken(), max_chars=1000)

    async def test_value_error_from_provider_is_not_disguised(self):
        class Broken:
            async def analyze(self, transcript):
                raise ValueError("bug")
        with self.assertRaisesRegex(ValueError, "bug"):
            await analyze_in_sections(sample(2), Broken(), max_chars=1000)


if __name__ == "__main__":
    unittest.main()
