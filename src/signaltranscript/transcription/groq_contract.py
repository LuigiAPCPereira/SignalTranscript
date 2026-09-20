"""Boundary validation for the Groq Whisper verbose_json segment payload.

This module performs no network calls and makes no assertion about account quotas.
Chunk overlap reconciliation belongs to a separate, explicitly tested step.
"""

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

MODEL = "whisper-large-v3-turbo"


class InvalidTranscription(ValueError):
    """A remote payload cannot be safely converted into a transcript."""


def transcription_options(language: str | None = None) -> dict[str, Any]:
    """Build the documented timestamp request options without supplying audio."""
    options: dict[str, Any] = {
        "model": MODEL,
        "response_format": "verbose_json",
        "timestamp_granularities": ["segment"],
    }
    if language is not None:
        if not isinstance(language, str) or len(language) != 2 or not language.isascii() or not language.isalpha():
            raise ValueError("language must be a two-letter ISO-639-1 code")
        options["language"] = language.lower()
    return options


def _milliseconds(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (float, int, str, Decimal)):
        raise InvalidTranscription(f"{field}: expected a finite number of seconds")
    try:
        seconds = Decimal(str(value))
    except InvalidOperation as exc:
        raise InvalidTranscription(f"{field}: invalid seconds") from exc
    if not seconds.is_finite() or seconds < 0:
        raise InvalidTranscription(f"{field}: seconds must be finite and nonnegative")
    return int((seconds * 1000).to_integral_value(rounding=ROUND_HALF_UP))


def normalize_segments(
    payload: Mapping[str, object], *, chunk_index: int = 0, chunk_offset_ms: int = 0
) -> list[dict[str, object]]:
    """Convert a single Groq verbose_json response to absolute-time segments.

    The caller must verify the audio chunk's actual offset. This function does
    not infer offsets, deduplicate overlaps or verify speech accuracy.
    """
    if isinstance(chunk_index, bool) or not isinstance(chunk_index, int) or chunk_index < 0:
        raise ValueError("chunk_index must be a nonnegative integer")
    if isinstance(chunk_offset_ms, bool) or not isinstance(chunk_offset_ms, int) or chunk_offset_ms < 0:
        raise ValueError("chunk_offset_ms must be a nonnegative integer")
    if not isinstance(payload, Mapping):
        raise InvalidTranscription("payload must be a mapping")
    raw_segments = payload.get("segments")
    if not isinstance(raw_segments, list) or not raw_segments:
        raise InvalidTranscription("verbose_json must contain a nonempty segments array")

    normalized: list[dict[str, object]] = []
    last_start = -1
    for position, segment in enumerate(raw_segments):
        if not isinstance(segment, Mapping):
            raise InvalidTranscription(f"segment {position}: expected an object")
        text = segment.get("text")
        if not isinstance(text, str) or not text.strip():
            raise InvalidTranscription(f"segment {position}: missing spoken text")
        start = _milliseconds(segment.get("start"), f"segment {position}.start")
        end = _milliseconds(segment.get("end"), f"segment {position}.end")
        if end <= start or start < last_start:
            raise InvalidTranscription(f"segment {position}: invalid or out-of-order interval")
        last_start = start
        normalized.append({
            "id": f"chunk-{chunk_index:04d}-seg-{position:04d}",
            "start_ms": chunk_offset_ms + start,
            "end_ms": chunk_offset_ms + end,
            "text": text,
        })
    return normalized
