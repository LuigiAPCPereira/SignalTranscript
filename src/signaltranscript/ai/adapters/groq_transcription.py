"""Groq speech-to-text adapter: SDK and HTTP details stop at this boundary.

It accepts an already-authorized local audio artifact. Acquisition, audio
chunking, job persistence and retry scheduling belong to other components.
"""

from collections.abc import Mapping
from math import isfinite
import os
from pathlib import Path
import stat
from typing import Any

from signaltranscript.ai.errors import ProviderFailure
from signaltranscript.ai.adapters.groq_errors import (
    retry_after as _retry_after, classify_sdk_error as _classify_sdk_error,
)
from signaltranscript.ai.ports import Segment, Transcript
from signaltranscript.transcription.groq_contract import (
    MODEL, InvalidTranscription, normalize_segments, transcription_options,
)

# Conservative free-tier preflight; actual per-account quota is not known here.
FREE_UPLOAD_LIMIT_BYTES = 25_000_000
SUPPORTED_EXTENSIONS = frozenset({
    ".flac", ".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".ogg", ".wav", ".webm",
})


def _payload_dict(response: object) -> Mapping[str, object]:
    if isinstance(response, Mapping):
        return response
    for name in ("to_dict", "model_dump"):
        method = getattr(response, name, None)
        if callable(method):
            data = method()
            if isinstance(data, Mapping):
                return data
    raise InvalidTranscription("unexpected response shape")


class GroqTranscriptionAdapter:
    """Implementation of TranscriptionProvider using an injected AsyncGroq client.

    No implicit provider fallback, no automatic retries, and no SDK types in
    Transcript. Only a single audio artifact is supported in this first slice.
    """

    def __init__(self, client: Any, *, max_upload_bytes: int = FREE_UPLOAD_LIMIT_BYTES,
                 owns_client: bool = False) -> None:
        if type(max_upload_bytes) is not int or max_upload_bytes <= 0:
            raise ValueError("max_upload_bytes must be a positive integer")
        self._client = client
        self._max_upload_bytes = max_upload_bytes
        self._owns_client = owns_client

    @classmethod
    def from_environment(cls, *, timeout_seconds: float = 180.0) -> "GroqTranscriptionAdapter":
        """Composition-root factory; called only when Groq has been selected."""
        key = os.environ.get("GROQ_API_KEY", "")
        if not key.strip():
            raise RuntimeError("GROQ_API_KEY is not configured")
        if not isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive and finite")
        from groq import AsyncGroq
        return cls(AsyncGroq(api_key=key, timeout=timeout_seconds, max_retries=0), owns_client=True)

    async def aclose(self) -> None:
        """Release the SDK connection pool if this adapter created it."""
        if self._owns_client:
            await self._client.close()

    async def transcribe(self, audio_path: Path, *, video_id: str,
                         language: str | None = None) -> Transcript:
        if not isinstance(video_id, str) or not video_id.strip():
            raise ValueError("video_id is required")
        options = transcription_options(language)
        path = Path(audio_path)
        try:
            file_info = path.lstat()
        except OSError:
            raise ProviderFailure("AUDIO_UNAVAILABLE") from None
        if not stat.S_ISREG(file_info.st_mode) or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise ProviderFailure("UNSUPPORTED_AUDIO")
        if file_info.st_size == 0:
            raise ProviderFailure("EMPTY_AUDIO")
        if file_info.st_size > self._max_upload_bytes:
            raise ProviderFailure("AUDIO_TOO_LARGE")

        try:
            response = await self._client.audio.transcriptions.create(file=path, **options)
        except Exception as exc:
            failure = _classify_sdk_error(exc)
            if failure is None:
                raise
            raise failure from None

        try:
            payload = _payload_dict(response)
            normalized = normalize_segments(payload)
            segments = tuple(Segment(id=item["id"], text=item["text"],
                                     start_ms=item["start_ms"], end_ms=item["end_ms"])
                             for item in normalized)
        except (InvalidTranscription, TypeError, ValueError) as exc:
            raise ProviderFailure("INVALID_RESPONSE") from None
        detected = payload.get("language")
        result_language = detected if isinstance(detected, str) and detected.strip() else language
        return Transcript(video_id=video_id, source="authorized_audio", segments=segments,
                          language=result_language, provider="groq", model=MODEL)
