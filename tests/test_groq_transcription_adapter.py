"""Offline contract tests: fake SDK calls never send files over the network."""

import asyncio
import os
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

from signaltranscript.ai.errors import ProviderFailure
from signaltranscript.ai.adapters.groq_transcription import (
    GroqTranscriptionAdapter, _retry_after,
)


class FakeTranscriptions:
    def __init__(self, payload=None, error=None):
        self.payload = payload if payload is not None else {
            "segments": [{"start": 0.25, "end": 1.5, "text": " Olá mundo!"}], "language": "portuguese",
        }
        self.error = error
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return SimpleNamespace(to_dict=lambda: self.payload)


class FakeStatusError(Exception):
    def __init__(self, status, headers=None):
        self.status_code = status
        self.response = SimpleNamespace(headers=headers or {})
        super().__init__("contains potentially sensitive provider response")


class AdapterTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.audio = Path(self.temp.name) / "audio.wav"
        self.audio.write_bytes(b"fixture-only-not-real-audio")
        self.transport = FakeTranscriptions()
        self.client = SimpleNamespace(audio=SimpleNamespace(transcriptions=self.transport))
        self.adapter = GroqTranscriptionAdapter(self.client)

    async def assert_failure(self, code, *, audio=None, error=None):
        if error is not None:
            self.transport.error = error
        with self.assertRaises(ProviderFailure) as caught:
            await self.adapter.transcribe(audio or self.audio, video_id="vid", language="pt")
        self.assertEqual(caught.exception.code, code)
        return caught.exception

    async def test_sends_documented_options_and_normalizes_to_neutral_transcript(self):
        transcript = await self.adapter.transcribe(self.audio, video_id="vid", language="PT")
        self.assertEqual(transcript.source, "authorized_audio")
        self.assertEqual((transcript.provider, transcript.model), ("groq", "whisper-large-v3-turbo"))
        self.assertEqual(transcript.language, "portuguese")  # do not invent ISO code
        self.assertEqual((transcript.segments[0].start_ms, transcript.segments[0].end_ms), (250, 1500))
        self.assertEqual(transcript.segments[0].text, " Olá mundo!")
        self.assertEqual(len(self.transport.calls), 1)
        self.assertEqual(self.transport.calls[0], {
            "file": self.audio, "model": "whisper-large-v3-turbo",
            "response_format": "verbose_json", "timestamp_granularities": ["segment"],
            "language": "pt",
        })

    async def test_auto_detect_does_not_set_language(self):
        await self.adapter.transcribe(self.audio, video_id="vid")
        self.assertNotIn("language", self.transport.calls[0])

    async def test_missing_audio_never_calls_provider(self):
        await self.assert_failure("AUDIO_UNAVAILABLE", audio=Path(self.temp.name) / "missing.wav")
        self.assertEqual(self.transport.calls, [])

    async def test_empty_unsupported_and_symlink_rejected_before_upload(self):
        empty = Path(self.temp.name) / "empty.wav"
        empty.touch()
        await self.assert_failure("EMPTY_AUDIO", audio=empty)
        bad = Path(self.temp.name) / "bad.exe"
        bad.write_bytes(b"stuff")
        await self.assert_failure("UNSUPPORTED_AUDIO", audio=bad)
        link = Path(self.temp.name) / "link.wav"
        link.symlink_to(self.audio)
        await self.assert_failure("UNSUPPORTED_AUDIO", audio=link)
        self.assertEqual(self.transport.calls, [])

    async def test_budget_rejected_before_upload_and_config_validated(self):
        adapter = GroqTranscriptionAdapter(self.client, max_upload_bytes=10)
        with self.assertRaises(ProviderFailure) as caught:
            await adapter.transcribe(self.audio, video_id="vid")
        self.assertEqual(caught.exception.code, "AUDIO_TOO_LARGE")
        self.assertEqual(self.transport.calls, [])
        with self.assertRaises(ValueError):
            GroqTranscriptionAdapter(self.client, max_upload_bytes=0)

    async def test_rate_limit_preserves_retry_after_without_retrying(self):
        error = await self.assert_failure("RATE_LIMITED", error=FakeStatusError(429, {"retry-after": "12.5"}))
        self.assertTrue(error.retryable)
        self.assertEqual(error.retry_after_seconds, 12.5)
        self.assertFalse(error.remote_outcome_unknown)
        self.assertEqual(len(self.transport.calls), 1)

    async def test_access_and_input_errors_are_permanent(self):
        for status, expected in ((401, "ACCESS_DENIED"), (403, "ACCESS_DENIED"),
                                 (413, "INVALID_REQUEST"), (404, "MODEL_UNAVAILABLE")):
            with self.subTest(status=status):
                self.transport.calls.clear()
                err = await self.assert_failure(expected, error=FakeStatusError(status))
                self.assertFalse(err.retryable)
                self.assertFalse(err.remote_outcome_unknown)
                self.assertEqual(len(self.transport.calls), 1)

    async def test_500_and_timeout_are_unknown_remote_outcomes(self):
        for error in (FakeStatusError(500), TimeoutError("possibly processed")):
            with self.subTest(error=type(error).__name__):
                self.transport.calls.clear()
                err = await self.assert_failure("REMOTE_UNAVAILABLE" if isinstance(error, FakeStatusError)
                                                else "REMOTE_OUTCOME_UNKNOWN", error=error)
                self.assertTrue(err.remote_outcome_unknown)
                self.assertTrue(err.retryable)
                self.assertEqual(len(self.transport.calls), 1)

    async def test_invalid_response_does_not_get_marked_success(self):
        self.transport.payload = {"text": "no segments"}
        error = await self.assert_failure("INVALID_RESPONSE")
        self.assertFalse(error.retryable)

    async def test_unexpected_programming_error_is_not_disguised(self):
        self.transport.error = AssertionError("programming bug")
        with self.assertRaisesRegex(AssertionError, "programming bug"):
            await self.adapter.transcribe(self.audio, video_id="vid")

    async def test_validation_before_transport(self):
        with self.assertRaises(ValueError):
            await self.adapter.transcribe(self.audio, video_id="", language="pt")
        with self.assertRaises(ValueError):
            await self.adapter.transcribe(self.audio, video_id="vid", language="pt-BR")
        self.assertEqual(self.transport.calls, [])

    async def test_does_not_close_an_injected_client(self):
        async def close():
            raise AssertionError("must not close externally owned SDK")
        self.client.close = close
        await self.adapter.aclose()

    def test_retry_after_is_bounded_and_never_uses_untrusted_header_string(self):
        for raw in ("NaN", "inf", "-2", "999999999", "Thu, 01 Jan 2030 00:00:00 GMT"):
            self.assertIsNone(_retry_after({"retry-after": raw}))
        self.assertIsNone(_retry_after(object()))

    def test_composition_factory_disables_sdk_retries_and_requires_key(self):
        class FakeAsyncGroq:
            def __init__(self, **kwargs):
                self.options = kwargs
                self.closed = False

            async def close(self):
                self.closed = True

        module = ModuleType("groq")
        module.AsyncGroq = FakeAsyncGroq
        with patch.dict(os.environ, {"GROQ_API_KEY": ""}):
            with self.assertRaisesRegex(RuntimeError, "not configured"):
                GroqTranscriptionAdapter.from_environment()
        with patch.dict(os.environ, {"GROQ_API_KEY": "fixture-key"}), patch.dict(sys.modules, {"groq": module}):
            adapter = GroqTranscriptionAdapter.from_environment(timeout_seconds=120)
            self.assertEqual(adapter._client.options["max_retries"], 0)
            self.assertEqual(adapter._client.options["timeout"], 120)
            asyncio.run(adapter.aclose())
            self.assertTrue(adapter._client.closed)


if __name__ == "__main__":
    unittest.main()
