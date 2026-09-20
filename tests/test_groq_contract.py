"""Offline boundary tests; these do not exercise Groq authentication or networking."""

import math
import unittest

from signaltranscript.transcription.groq_contract import (
    InvalidTranscription,
    normalize_segments,
    transcription_options,
)


class GroqContractTests(unittest.TestCase):
    def test_request_uses_verbose_json_and_segment_timestamps(self) -> None:
        self.assertEqual(transcription_options("PT"), {
            "model": "whisper-large-v3-turbo",
            "response_format": "verbose_json",
            "timestamp_granularities": ["segment"],
            "language": "pt",
        })

    def test_language_not_guessed(self) -> None:
        self.assertNotIn("language", transcription_options())
        with self.assertRaises(ValueError):
            transcription_options("pt-BR")

    def test_timestamp_offsets_are_absolute_and_text_is_preserved(self) -> None:
        segments = normalize_segments({"segments": [
            {"id": 8, "start": 0.125, "end": 1.25, "text": " Olá."},
            {"start": 1.25, "end": 2.0, "text": " Mundo!"},
        ]}, chunk_index=2, chunk_offset_ms=60_000)
        self.assertEqual(segments, [
            {"id": "chunk-0002-seg-0000", "start_ms": 60125, "end_ms": 61250, "text": " Olá."},
            {"id": "chunk-0002-seg-0001", "start_ms": 61250, "end_ms": 62000, "text": " Mundo!"},
        ])

    def test_milliseconds_round_half_up(self) -> None:
        out = normalize_segments({"segments": [{"start": 0.0005, "end": 0.0015, "text": "a"}]})
        self.assertEqual((out[0]["start_ms"], out[0]["end_ms"]), (1, 2))

    def test_rejects_missing_or_empty_segments(self) -> None:
        for payload in ({}, {"segments": []}, {"segments": "not a list"}):
            with self.subTest(payload=payload), self.assertRaises(InvalidTranscription):
                normalize_segments(payload)

    def test_rejects_bad_timestamp_and_blank_text(self) -> None:
        for segment in (
            {"start": 0, "end": 1, "text": " "},
            {"start": 1, "end": 1, "text": "a"},
            {"start": -1, "end": 1, "text": "a"},
            {"start": math.nan, "end": 1, "text": "a"},
            {"start": 0, "end": math.inf, "text": "a"},
            {"start": True, "end": 1, "text": "a"},
            {"end": 1, "text": "a"},
        ):
            with self.subTest(segment=segment), self.assertRaises(InvalidTranscription):
                normalize_segments({"segments": [segment]})

    def test_rejects_out_of_order_segments(self) -> None:
        with self.assertRaises(InvalidTranscription):
            normalize_segments({"segments": [
                {"start": 3, "end": 4, "text": "a"},
                {"start": 2, "end": 2.5, "text": "b"},
            ]})

    def test_rejects_invalid_offsets_without_network(self) -> None:
        for kwargs in ({"chunk_offset_ms": -1}, {"chunk_index": True}, {"chunk_offset_ms": 0.5}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                normalize_segments({"segments": [{"start": 0, "end": 1, "text": "a"}]}, **kwargs)


if __name__ == "__main__":
    unittest.main()
