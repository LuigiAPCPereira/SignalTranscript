"""Offline provider substitution tests: no SDK, network or real local model."""

import asyncio
from pathlib import Path
import unittest

from signaltranscript.ai.ports import Analysis, Idea, Segment, Transcript, validate_analysis
from signaltranscript.ai.selection import ProviderSelection, select_providers


class FakeTranscriber:
    def __init__(self, name: str):
        self.name = name
        self.calls = 0

    async def transcribe(self, audio_path: Path, *, video_id: str, language: str | None = None) -> Transcript:
        self.calls += 1
        return Transcript(
            video_id=video_id,
            source="authorized_audio",
            language=language,
            provider=self.name,
            model="fixture",
            segments=(Segment("segment-1", "spoken content", 0, 1500),),
        )


class FakeAnalyzer:
    def __init__(self, name: str):
        self.name = name
        self.calls = 0

    async def analyze(self, transcript: Transcript) -> Analysis:
        self.calls += 1
        return Analysis(
            summary="summary",
            ideas=(Idea("idea", "explanation", (transcript.segments[0].id,)),),
            provider=self.name,
            model="fixture",
        )


class BoundaryTests(unittest.TestCase):
    def setUp(self):
        self.groq = FakeTranscriber("groq")
        self.local = FakeTranscriber("local")
        self.groq_llm = FakeAnalyzer("groq")
        self.nim = FakeAnalyzer("nim")
        self.transcribers = {"groq": self.groq, "local": self.local}
        self.analyzers = {"groq": self.groq_llm, "nim": self.nim}

    def test_independent_choice_and_canonical_result(self):
        chosen = select_providers(
            ProviderSelection("local", "nim"),
            transcribers=self.transcribers, analyzers=self.analyzers,
        )
        transcript = asyncio.run(chosen.transcription.transcribe(Path("/nonexistent-fixture.wav"), video_id="v1", language="pt"))
        analysis = asyncio.run(chosen.analysis.analyze(transcript))
        validate_analysis(transcript, analysis)
        self.assertEqual((transcript.provider, analysis.provider), ("local", "nim"))
        self.assertEqual((self.groq.calls, self.groq_llm.calls), (0, 0))

    def test_change_only_analyzer(self):
        chosen = select_providers(
            ProviderSelection("groq", "nim"),
            transcribers=self.transcribers, analyzers=self.analyzers,
        )
        self.assertIs(chosen.transcription, self.groq)
        self.assertIs(chosen.analysis, self.nim)

    def test_unknown_transcriber_does_not_fallback(self):
        with self.assertRaisesRegex(ValueError, "unconfigured transcription provider"):
            select_providers(ProviderSelection("paid", "groq"), transcribers=self.transcribers, analyzers=self.analyzers)
        self.assertEqual(self.groq.calls, 0)

    def test_unknown_analyzer_does_not_fallback(self):
        with self.assertRaisesRegex(ValueError, "unconfigured analysis provider"):
            select_providers(ProviderSelection("groq", "paid"), transcribers=self.transcribers, analyzers=self.analyzers)
        self.assertEqual(self.groq_llm.calls, 0)

    def test_missing_timestamp_is_not_invented(self):
        segment = Segment("s", "content", None, None)
        self.assertIsNone(segment.start_ms)
        with self.assertRaises(ValueError):
            Segment("s", "content", 0, None)

    def test_invalid_interval_rejected(self):
        for start, end in [(1, 1), (-1, 1), (True, 2)]:
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                Segment("s", "text", start, end)

    def test_duplicate_ids_rejected(self):
        with self.assertRaisesRegex(ValueError, "unique"):
            Transcript("v1", "manual_import", (Segment("s", "text", None, None), Segment("s", "text", None, None)))

    def test_unsupported_reference_rejected(self):
        transcript = Transcript("v1", "manual_import", (Segment("s", "spoken", None, None),))
        analysis = Analysis("summary", (Idea("idea", "detail", ("other-video",)),), "nim", "fixture")
        with self.assertRaisesRegex(ValueError, "unknown transcript segment"):
            validate_analysis(transcript, analysis)

    def test_empty_evidence_rejected(self):
        transcript = Transcript("v1", "manual_import", (Segment("s", "spoken", None, None),))
        analysis = Analysis("summary", (Idea("idea", "detail", ()),), "groq", "fixture")
        with self.assertRaisesRegex(ValueError, "evidence"):
            validate_analysis(transcript, analysis)


if __name__ == "__main__":
    unittest.main()
