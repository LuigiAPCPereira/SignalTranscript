"""Provider-independent application contracts.

Acquisition/import may construct Transcript directly without calling speech-to-text.
Concrete Groq, NIM or local adapters implement the ports separately.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True, slots=True)
class Segment:
    id: str
    text: str
    start_ms: int | None
    end_ms: int | None

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.text.strip():
            raise ValueError("segment ID and text must not be blank")
        if (self.start_ms is None) != (self.end_ms is None):
            raise ValueError("segment timestamps must both be present or absent")
        if self.start_ms is not None:
            if (type(self.start_ms) is not int or type(self.end_ms) is not int
                    or self.start_ms < 0 or self.end_ms <= self.start_ms):
                raise ValueError("segment interval is invalid")


@dataclass(frozen=True, slots=True)
class Transcript:
    video_id: str
    source: str
    segments: tuple[Segment, ...]
    language: str | None = None
    provider: str | None = None
    model: str | None = None

    def __post_init__(self) -> None:
        if not self.video_id.strip() or not self.source.strip() or not self.segments:
            raise ValueError("transcript needs a video, source and segments")
        if len({segment.id for segment in self.segments}) != len(self.segments):
            raise ValueError("segment IDs must be unique within a transcript")


@dataclass(frozen=True, slots=True)
class Idea:
    title: str
    explanation: str
    source_segment_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Analysis:
    summary: str
    ideas: tuple[Idea, ...]
    provider: str
    model: str


def validate_analysis(transcript: Transcript, analysis: Analysis) -> None:
    """Reject invalid evidence references; factual verification is separate."""
    if not analysis.summary.strip() or not analysis.provider.strip() or not analysis.model.strip():
        raise ValueError("analysis metadata and summary are required")
    allowed = {segment.id for segment in transcript.segments}
    for idea in analysis.ideas:
        if not idea.title.strip() or not idea.explanation.strip() or not idea.source_segment_ids:
            raise ValueError("each idea needs text and evidence references")
        if any(segment_id not in allowed for segment_id in idea.source_segment_ids):
            raise ValueError("idea references an unknown transcript segment")


class TranscriptionProvider(Protocol):
    async def transcribe(self, audio_path: Path, *, video_id: str, language: str | None = None) -> Transcript:
        """Transcribe authorized audio into the canonical representation."""
        ...


class AnalysisProvider(Protocol):
    async def analyze(self, transcript: Transcript) -> Analysis:
        """Analyze a canonical transcript independently of STT or acquisition."""
        ...
