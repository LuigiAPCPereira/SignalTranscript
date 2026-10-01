"""Offline contracts for durable global synthesis checkpoints."""

from pathlib import Path
import sqlite3
import tempfile
import unittest

from signaltranscript.ai.long_form import AnalyzedSection, SectionedAnalysis
from signaltranscript.ai.ports import Analysis, Idea, Segment, Transcript
from signaltranscript.ai.synthesis_checkpoint import (
    SQLiteGlobalSynthesisCheckpoint, SynthesisCheckpointMismatch,
    synthesize_with_checkpoint,
)


def source() -> Transcript:
    return Transcript(
        "video-one", "manual_import",
        tuple(Segment(f"s{i}", f"segmento {i}", i * 1000, (i + 1) * 1000) for i in range(9)),
        language="pt-BR",
    )


def sections() -> SectionedAnalysis:
    items = []
    for index in range(3):
        ids = tuple(f"s{i}" for i in range(index * 3, index * 3 + 3))
        items.append(AnalyzedSection(
            index, ids,
            Analysis(f"Seção {index}", (Idea(f"Tema {index}", "Local", (ids[0],)),),
                     "section-fake", "section-model"),
        ))
    return SectionedAnalysis("video-one", 3, tuple(items))


def global_analysis(*refs: str, summary: str = "Síntese global") -> Analysis:
    return Analysis(summary, (Idea("Tema", "Global", tuple(refs)),), "global-fake", "global-model")


class FakeProvider:
    def __init__(self, analysis: Analysis) -> None:
        self.analysis = analysis
        self.calls = 0

    async def synthesize(self, transcript, sectioned):
        self.calls += 1
        return self.analysis


class SynthesisCheckpointTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "analysis.db"

    def tearDown(self):
        self.tmp.cleanup()

    def checkpoint(self, **overrides):
        values = dict(run_id="run-1", transcript=source(), sectioned=sections(),
                      provider="global-fake", model="global-model", revision="prompt-v1")
        values.update(overrides)
        return SQLiteGlobalSynthesisCheckpoint(self.path, **values)

    async def test_persists_and_reuses_validated_global_synthesis_without_second_call(self):
        provider = FakeProvider(global_analysis("s0", "s4", "s8"))
        first = await synthesize_with_checkpoint(self.checkpoint(), provider)
        second = await synthesize_with_checkpoint(self.checkpoint(), provider)
        self.assertEqual(provider.calls, 1)
        self.assertEqual(first, second)
        self.assertTrue(second.coverage.spans_all_positions)

    async def test_changed_revision_refuses_stale_result_before_provider_call(self):
        provider = FakeProvider(global_analysis("s0", "s4", "s8"))
        await synthesize_with_checkpoint(self.checkpoint(), provider)
        changed = self.checkpoint(revision="prompt-v2")
        other = FakeProvider(global_analysis("s0", "s4", "s8"))
        with self.assertRaises(SynthesisCheckpointMismatch) as caught:
            await synthesize_with_checkpoint(changed, other)
        self.assertEqual(caught.exception.args[0], "RUN_CONFIGURATION_CHANGED")
        self.assertEqual(other.calls, 0)

    async def test_invalid_positional_result_is_never_persisted(self):
        provider = FakeProvider(global_analysis("s0", "s8"))
        with self.assertRaises(Exception):
            await synthesize_with_checkpoint(self.checkpoint(), provider)
        self.assertIsNone(self.checkpoint().load())

    async def test_provider_identity_mismatch_is_not_persisted(self):
        wrong = Analysis("Síntese", (Idea("Tema", "Global", ("s0", "s4", "s8")),),
                         "other", "model")
        with self.assertRaises(SynthesisCheckpointMismatch) as caught:
            await synthesize_with_checkpoint(self.checkpoint(), FakeProvider(wrong))
        self.assertEqual(caught.exception.args[0], "PROVIDER_CHANGED")
        self.assertIsNone(self.checkpoint().load())

    async def test_different_transcript_with_same_run_id_fails_closed(self):
        await synthesize_with_checkpoint(
            self.checkpoint(), FakeProvider(global_analysis("s0", "s4", "s8")),
        )
        changed = source()
        changed = Transcript(changed.video_id, changed.source,
                             changed.segments[:-1] + (Segment("s8", "alterado", 8000, 9000),),
                             language=changed.language)
        with self.assertRaises(SynthesisCheckpointMismatch) as caught:
            self.checkpoint(transcript=changed).load()
        self.assertEqual(caught.exception.args[0], "RUN_CONFIGURATION_CHANGED")


    async def test_historical_read_uses_stored_identity_not_current_configuration(self):
        await synthesize_with_checkpoint(
            self.checkpoint(), FakeProvider(global_analysis("s0", "s4", "s8")),
        )
        restored = SQLiteGlobalSynthesisCheckpoint.load_persisted(
            self.path, run_id="run-1", transcript=source(), sectioned=sections(),
        )
        self.assertIsNotNone(restored)
        self.assertEqual(restored.analysis.provider, "global-fake")
        self.assertEqual(restored.analysis.model, "global-model")
        self.assertTrue(restored.coverage.spans_all_positions)

    async def test_historical_read_fails_closed_on_changed_source(self):
        await synthesize_with_checkpoint(
            self.checkpoint(), FakeProvider(global_analysis("s0", "s4", "s8")),
        )
        changed = source()
        changed = Transcript(
            changed.video_id, changed.source,
            changed.segments[:-1] + (Segment("s8", "changed", 8000, 9000),),
            language=changed.language,
        )
        with self.assertRaises(SynthesisCheckpointMismatch) as caught:
            SQLiteGlobalSynthesisCheckpoint.load_persisted(
                self.path, run_id="run-1", transcript=changed, sectioned=sections(),
            )
        self.assertEqual(caught.exception.args[0], "RUN_CONFIGURATION_CHANGED")

    async def test_corrupted_payload_is_rejected(self):
        await synthesize_with_checkpoint(
            self.checkpoint(), FakeProvider(global_analysis("s0", "s4", "s8")),
        )
        conn = sqlite3.connect(self.path)
        try:
            with conn:
                conn.execute("UPDATE global_syntheses SET payload='{}' WHERE run_id='run-1'")
        finally:
            conn.close()
        with self.assertRaises(SynthesisCheckpointMismatch) as caught:
            self.checkpoint().load()
        self.assertEqual(caught.exception.args[0], "INVALID_SYNTHESIS_PAYLOAD")

    async def test_rewrite_with_different_valid_result_is_forbidden(self):
        checkpoint = self.checkpoint()
        await synthesize_with_checkpoint(
            checkpoint, FakeProvider(global_analysis("s0", "s4", "s8")),
        )
        from signaltranscript.ai.coverage import assess_reference_positions
        from signaltranscript.ai.synthesis import GlobalSynthesis
        alternate = global_analysis("s0", "s4", "s8", summary="Outra síntese")
        coverage = assess_reference_positions(source(), tuple(s.segment_ids for s in sections().sections),
                                              ("s0", "s4", "s8"))
        with self.assertRaises(SynthesisCheckpointMismatch) as caught:
            checkpoint.save(GlobalSynthesis(alternate, coverage))
        self.assertEqual(caught.exception.args[0], "SYNTHESIS_REWRITE_FORBIDDEN")


if __name__ == "__main__":
    unittest.main()
