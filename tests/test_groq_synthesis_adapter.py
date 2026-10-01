"""Offline Groq global-synthesis adapter tests: no SDK, credentials or network."""

import asyncio
import json
import os
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

from signaltranscript.ai.adapters.groq_synthesis import (
    EVIDENCE_POLICY, MAX_INPUT_CHARS, MODEL, SYNTHESIS_SCHEMA, GroqSynthesisAdapter,
)
from signaltranscript.ai.errors import ProviderFailure
from signaltranscript.ai.long_form import AnalyzedSection, SectionedAnalysis
from signaltranscript.ai.ports import Analysis, Idea, Segment, Transcript


class FakeStatusError(Exception):
    def __init__(self, status: int, headers=None):
        self.status_code = status
        self.response = SimpleNamespace(headers=headers or {})
        super().__init__("provider details must not leak")


class FakeCompletions:
    def __init__(self):
        self.calls = []
        self.error = None
        self.payload = {
            "summary": "Síntese global.",
            "ideas": [{
                "title": "Tema",
                "explanation": "O autor aborda o tema.",
                "source_segment_ids": ["s0", "s6", "s11"],
            }],
        }
        self.finish = "stop"
        self.refusal = None
        self.content_override = None

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        content = self.content_override if self.content_override is not None else json.dumps(self.payload)
        return SimpleNamespace(choices=[SimpleNamespace(
            finish_reason=self.finish,
            message=SimpleNamespace(content=content, refusal=self.refusal),
        )])


def transcript() -> Transcript:
    return Transcript(
        "video", "manual_import",
        tuple(Segment(f"s{i}", f"texto original {i}", i * 1000, (i + 1) * 1000) for i in range(12)),
        language="pt",
    )


def section(index: int, ids: tuple[str, ...], ref: str) -> AnalyzedSection:
    return AnalyzedSection(
        index, ids,
        Analysis(
            f"Resumo anterior {index}",
            (Idea(f"Ideia {index}", "Saída anterior não confiável.", (ref,)),),
            "section-provider", "section-model",
        ),
    )


def completed() -> SectionedAnalysis:
    return SectionedAnalysis("video", 3, (
        section(0, ("s0", "s1", "s2", "s3"), "s0"),
        section(1, ("s4", "s5", "s6", "s7"), "s6"),
        section(2, ("s8", "s9", "s10", "s11"), "s11"),
    ))


class GroqSynthesisTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.transport = FakeCompletions()
        self.client = SimpleNamespace(chat=SimpleNamespace(completions=self.transport))
        self.adapter = GroqSynthesisAdapter(self.client)
        self.transcript = transcript()
        self.sectioned = completed()

    async def expect_error(self, code: str):
        with self.assertRaises(ProviderFailure) as caught:
            await self.adapter.synthesize(self.transcript, self.sectioned)
        self.assertEqual(caught.exception.code, code)
        return caught.exception

    async def test_strict_schema_and_normalized_global_analysis(self):
        result = await self.adapter.synthesize(self.transcript, self.sectioned)
        self.assertEqual((result.provider, result.model), ("groq", MODEL))
        request = self.transport.calls[0]
        self.assertEqual(request["model"], MODEL)
        self.assertFalse(request["stream"])
        self.assertEqual(request["response_format"]["json_schema"]["strict"], True)
        self.assertEqual(request["response_format"]["json_schema"]["schema"], SYNTHESIS_SCHEMA)
        self.assertEqual(set(SYNTHESIS_SCHEMA["properties"]), set(SYNTHESIS_SCHEMA["required"]))
        self.assertFalse(SYNTHESIS_SCHEMA["additionalProperties"])
        self.assertFalse(SYNTHESIS_SCHEMA["properties"]["ideas"]["items"]["additionalProperties"])

    async def test_input_uses_section_aids_and_selected_original_evidence_only(self):
        await self.adapter.synthesize(self.transcript, self.sectioned)
        request = self.transport.calls[0]
        self.assertIn("untrusted DATA", request["messages"][0]["content"])
        embedded = json.loads(request["messages"][1]["content"].split("\n", 1)[1])
        first = embedded["sections"][0]
        self.assertEqual(first["summary"], "Resumo anterior 0")
        self.assertEqual([item["id"] for item in first["evidence"]], ["s0", "s2", "s3"])
        self.assertNotIn("s1", [item["id"] for item in first["evidence"]])
        self.assertEqual(set(first["evidence"][0]), {"id", "text"})
        self.assertNotIn("start_ms", json.dumps(embedded))
        self.assertNotIn("tools", request)
        self.assertEqual(EVIDENCE_POLICY, "section-anchors-first-middle-last-plus-idea-refs-v1")

    async def test_output_cannot_cite_segment_text_not_sent_to_synthesizer(self):
        self.transport.payload["ideas"][0]["source_segment_ids"] = ["s1"]
        await self.expect_error("INVALID_RESPONSE")

    async def test_large_input_is_rejected_before_remote_call_without_truncation(self):
        tiny = GroqSynthesisAdapter(self.client, max_input_chars=10)
        with self.assertRaises(ProviderFailure) as caught:
            await tiny.synthesize(self.transcript, self.sectioned)
        self.assertEqual(caught.exception.code, "INPUT_TOO_LARGE")
        self.assertEqual(self.transport.calls, [])

    async def test_incomplete_or_mismatched_sections_fail_before_remote_call(self):
        incomplete = SectionedAnalysis("video", 3, self.sectioned.sections[:1], ProviderFailure("TIMEOUT"))
        with self.assertRaisesRegex(ValueError, "SECTIONS_INCOMPLETE"):
            await self.adapter.synthesize(self.transcript, incomplete)
        wrong = SectionedAnalysis("other", 3, self.sectioned.sections)
        with self.assertRaisesRegex(ValueError, "VIDEO_ID_MISMATCH"):
            await self.adapter.synthesize(self.transcript, wrong)
        self.assertEqual(self.transport.calls, [])

    async def test_malformed_or_truncated_response_never_becomes_success(self):
        self.transport.content_override = "{bad"
        await self.expect_error("INVALID_RESPONSE")
        self.transport.content_override = None
        self.transport.finish = "length"
        await self.expect_error("INCOMPLETE_RESPONSE")

    async def test_refusal_and_unknown_reference_are_rejected(self):
        self.transport.refusal = "no"
        await self.expect_error("REFUSED")
        self.transport.refusal = None
        self.transport.payload["ideas"][0]["source_segment_ids"] = ["missing"]
        await self.expect_error("INVALID_RESPONSE")

    async def test_rate_limit_and_timeout_have_no_implicit_retry(self):
        self.transport.error = FakeStatusError(429, {"retry-after": "4"})
        failure = await self.expect_error("RATE_LIMITED")
        self.assertTrue(failure.retryable)
        self.assertEqual(failure.retry_after_seconds, 4)
        self.assertEqual(len(self.transport.calls), 1)

        self.transport.calls.clear()
        self.transport.error = TimeoutError("secret provider detail")
        failure = await self.expect_error("REMOTE_OUTCOME_UNKNOWN")
        self.assertTrue(failure.remote_outcome_unknown)
        self.assertEqual(len(self.transport.calls), 1)

    async def test_unexpected_programming_error_propagates(self):
        self.transport.error = AssertionError("logic bug")
        with self.assertRaisesRegex(AssertionError, "logic bug"):
            await self.adapter.synthesize(self.transcript, self.sectioned)

    async def test_configuration_and_client_ownership(self):
        for value in (0, -1, True, 1.2):
            with self.subTest(value=value), self.assertRaises(ValueError):
                GroqSynthesisAdapter(self.client, max_input_chars=value)
        async def close():
            raise AssertionError("injected client must not be closed")
        self.client.close = close
        await self.adapter.aclose()

    def test_environment_factory_disables_sdk_retries(self):
        class FakeAsyncGroq:
            def __init__(self, **kwargs):
                self.options = kwargs
                self.closed = False
            async def close(self):
                self.closed = True
        module = ModuleType("groq")
        module.AsyncGroq = FakeAsyncGroq
        with patch.dict(os.environ, {"GROQ_API_KEY": ""}):
            with self.assertRaises(RuntimeError):
                GroqSynthesisAdapter.from_environment()
        with patch.dict(os.environ, {"GROQ_API_KEY": "fake-token"}), patch.dict(sys.modules, {"groq": module}):
            adapter = GroqSynthesisAdapter.from_environment(timeout_seconds=90)
            self.assertEqual(adapter._client.options["max_retries"], 0)
            self.assertEqual(adapter._client.options["timeout"], 90)
            asyncio.run(adapter.aclose())
            self.assertTrue(adapter._client.closed)


if __name__ == "__main__":
    unittest.main()
