"""SQLite checkpoint contract tests: no Groq SDK, credentials or network."""

import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from signaltranscript.ai.errors import ProviderFailure
from signaltranscript.ai.long_form import AnalyzedSection, ChunkPlanningError
from signaltranscript.ai.ports import Analysis, Idea, Segment, Transcript
from signaltranscript.ai.section_checkpoint import (
    CheckpointMismatch, SQLiteSectionCheckpoint, analyze_with_checkpoint,
)


def sample(*, text="conteúdo", count=7, source="manual_caption"):
    return Transcript("video-1", source, tuple(
        Segment(f"s{i}", f"{text} {i}" * 6, i * 1000, (i + 1) * 1000)
        for i in range(count)), "pt-BR")


class Fake:
    def __init__(self, *, failure_at=None, remote_unknown=False, model="model-v1", bad_ref=False):
        self.calls = []
        self.failure_at = failure_at
        self.remote_unknown = remote_unknown
        self.model = model
        self.bad_ref = bad_ref

    async def analyze(self, part):
        idx = len(self.calls)
        self.calls.append(part)
        if idx == self.failure_at:
            raise ProviderFailure("TIMEOUT" if self.remote_unknown else "RATE_LIMITED",
                                  retryable=True, remote_outcome_unknown=self.remote_unknown)
        ref = "unknown" if self.bad_ref else part.segments[0].id
        return Analysis("Resumo do trecho", (Idea("Ideia", "Explicação", (ref,)),),
                        "fake", self.model)


class CheckpointTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "sections.sqlite3"
        self.transcript = sample()

    def store(self, *, transcript=None, run_id="run-1", provider="fake",
              model="model-v1", revision="prompt1-schema1", max_chars=190):
        return SQLiteSectionCheckpoint(
            self.path, run_id=run_id, transcript=transcript or self.transcript,
            provider=provider, model=model, revision=revision, max_chars=max_chars,
        )

    async def test_resume_after_failure_reuses_prefix_without_remote_calls(self):
        first = self.store()
        self.assertGreater(len(first.planned), 2)
        failed = await analyze_with_checkpoint(first, Fake(failure_at=1))
        self.assertFalse(failed.complete)
        self.assertEqual(len(failed.sections), 1)
        self.assertEqual(len(first.open_and_load()), 1)

        reopened = self.store()
        remaining = Fake()
        result = await analyze_with_checkpoint(reopened, remaining)
        self.assertTrue(result.complete)
        self.assertEqual(len(remaining.calls), result.planned_sections - 1)
        self.assertEqual(tuple(s for section in result.sections for s in section.segment_ids),
                         tuple(s.id for s in self.transcript.segments))
        self.assertEqual(result.sections[0], failed.sections[0])
        self.assertFalse(hasattr(result, "summary"))

    async def test_complete_run_never_calls_provider_again(self):
        first = await analyze_with_checkpoint(self.store(), Fake())
        self.assertTrue(first.complete)
        again = Fake()
        second = await analyze_with_checkpoint(self.store(), again)
        self.assertEqual(again.calls, [])
        self.assertEqual(second, first)

    async def test_remote_unknown_is_uncommitted_and_not_success(self):
        result = await analyze_with_checkpoint(self.store(), Fake(failure_at=1, remote_unknown=True))
        self.assertFalse(result.complete)
        self.assertTrue(result.failure.remote_outcome_unknown)
        self.assertEqual(len(self.store().open_and_load()), 1)

    async def test_stale_transcript_or_plan_or_revision_rejected_before_remote(self):
        await analyze_with_checkpoint(self.store(), Fake(failure_at=1))
        changes = [
            {"transcript": sample(text="alterado")},
            {"transcript": sample(source="user_import")},
            {"transcript": Transcript("video-1", "manual_caption", tuple(
                Segment(seg.id, seg.text, seg.start_ms + 10, seg.end_ms + 10)
                for seg in self.transcript.segments), "pt-BR")},
            {"revision": "new-prompt"},
            {"provider": "alternative"},
            {"model": "other"},
            {"max_chars": 500},
        ]
        for settings in changes:
            with self.subTest(settings=settings):
                provider = Fake()
                with self.assertRaises(CheckpointMismatch) as caught:
                    await analyze_with_checkpoint(self.store(**settings), provider)
                self.assertEqual(caught.exception.args[0], "RUN_CONFIGURATION_CHANGED")
                self.assertEqual(provider.calls, [])

    async def test_separate_run_ids_allow_versioning(self):
        a = await analyze_with_checkpoint(self.store(run_id="v1"), Fake())
        b = await analyze_with_checkpoint(self.store(run_id="v2", revision="new"), Fake())
        self.assertTrue(a.complete and b.complete)
        with sqlite3.connect(self.path) as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM analysis_runs").fetchone()[0], 2)

    async def test_corrupt_payload_detected_before_remote(self):
        await analyze_with_checkpoint(self.store(), Fake(failure_at=1))
        with sqlite3.connect(self.path) as conn:
            conn.execute("UPDATE analysis_sections SET payload='{}' WHERE section_index=0")
        provider = Fake()
        with self.assertRaises(CheckpointMismatch):
            await analyze_with_checkpoint(self.store(), provider)
        self.assertEqual(provider.calls, [])

    async def test_invalid_evidence_in_checkpoint_detected_before_remote(self):
        await analyze_with_checkpoint(self.store(), Fake(failure_at=1))
        with sqlite3.connect(self.path) as conn:
            row = conn.execute("SELECT payload FROM analysis_sections WHERE section_index=0").fetchone()
            payload = json.loads(row[0])
            payload["analysis"]["ideas"][0]["source_segment_ids"] = ["foreign"]
            conn.execute("UPDATE analysis_sections SET payload=? WHERE section_index=0",
                         (json.dumps(payload),))
        provider = Fake()
        with self.assertRaisesRegex(CheckpointMismatch, "INVALID_CHECKPOINT_EVIDENCE"):
            await analyze_with_checkpoint(self.store(), provider)
        self.assertEqual(provider.calls, [])

    async def test_noncontiguous_checkpoint_detected(self):
        await analyze_with_checkpoint(self.store(), Fake(failure_at=2))
        with sqlite3.connect(self.path) as conn:
            conn.execute("UPDATE analysis_sections SET section_index=4 WHERE section_index=1")
        with self.assertRaisesRegex(CheckpointMismatch, "NONCONTIGUOUS_CHECKPOINT"):
            self.store().open_and_load()

    async def test_idempotent_save_and_different_rewrite_forbidden(self):
        first = await analyze_with_checkpoint(self.store(), Fake(failure_at=1))
        store = self.store()
        store.save(first.sections[0])
        changed = AnalyzedSection(0, first.sections[0].segment_ids,
                                  Analysis("Mudou", first.sections[0].analysis.ideas,
                                           "fake", "model-v1"))
        with self.assertRaisesRegex(CheckpointMismatch, "CHECKPOINT_REWRITE_FORBIDDEN"):
            store.save(changed)
        self.assertEqual(store.open_and_load(), first.sections)

    async def test_out_of_order_and_bad_provider_rejected(self):
        store = self.store()
        store.open_and_load()
        item = AnalyzedSection(1, tuple(s.id for s in store.planned[1].segments),
                               Analysis("Resumo", (Idea("T", "E", (store.planned[1].segments[0].id,)),),
                                        "fake", "model-v1"))
        with self.assertRaisesRegex(CheckpointMismatch, "CHECKPOINT_OUT_OF_ORDER"):
            store.save(item)
        with self.assertRaisesRegex(CheckpointMismatch, "PROVIDER_CHANGED"):
            store.save(AnalyzedSection(0, tuple(s.id for s in store.planned[0].segments),
                                       Analysis("R", (), "external", "model-v1")))

    async def test_provider_change_from_adapter_stops_with_no_checkpoint(self):
        with self.assertRaisesRegex(CheckpointMismatch, "PROVIDER_CHANGED"):
            await analyze_with_checkpoint(self.store(), Fake(model="different"))
        self.assertEqual(self.store().open_and_load(), ())

    async def test_invalid_model_output_is_not_stored(self):
        result = await analyze_with_checkpoint(self.store(), Fake(bad_ref=True))
        self.assertFalse(result.complete)
        self.assertEqual(result.failure.code, "INVALID_RESPONSE")
        self.assertEqual(self.store().open_and_load(), ())

    async def test_oversize_preflight_does_not_create_db(self):
        oversized = sample(text="x" * 2000)
        with self.assertRaises(ChunkPlanningError):
            self.store(transcript=oversized)
        self.assertFalse(self.path.exists())

    async def test_storage_failure_is_not_masked(self):
        store = self.store()
        store.path = Path(self.temp.name) / "missing-parent" / "db.sqlite3"
        with self.assertRaises(sqlite3.OperationalError):
            await analyze_with_checkpoint(store, Fake())

    async def test_invalid_identifiers_rejected(self):
        for name in ("run_id", "provider", "model", "revision"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.store(**{name: "  "})


if __name__ == "__main__":
    unittest.main()
