"""Read-only local library projection over the persistent job journal.

The journal remains the source of truth.  This module groups immutable transcript
versions by video_id and searches only the latest persisted transcript per video.
No provider, acquisition, checkpoint mutation, or deep-link decision lives here.
"""

from dataclasses import dataclass

from signaltranscript.ai.ports import Segment
from signaltranscript.backend.jobs import Job, SQLiteJobs


@dataclass(frozen=True, slots=True)
class LibraryEntry:
    latest_job: Job
    version_count: int


@dataclass(frozen=True, slots=True)
class TranscriptSearchHit:
    job: Job
    segment: Segment


class LibraryReadModel:
    """Exact local read model; intentionally derived instead of duplicated."""

    def __init__(self, jobs: SQLiteJobs) -> None:
        self._jobs = jobs

    def _all_jobs(self) -> tuple[Job, ...]:
        collected: list[Job] = []
        before: int | None = None
        while True:
            page, next_before = self._jobs.list_jobs(limit=50, before=before)
            collected.extend(page)
            if next_before is None:
                return tuple(collected)
            if before is not None and next_before >= before:
                raise RuntimeError("INVALID_JOB_PAGINATION")
            before = next_before

    def _entries(self) -> tuple[LibraryEntry, ...]:
        latest: dict[str, Job] = {}
        counts: dict[str, int] = {}
        # list_jobs is newest-first, so setdefault preserves the current version.
        for job in self._all_jobs():
            video_id = job.transcript.video_id
            counts[video_id] = counts.get(video_id, 0) + 1
            latest.setdefault(video_id, job)
        entries = [
            LibraryEntry(job, counts[video_id])
            for video_id, job in latest.items()
        ]
        entries.sort(key=lambda entry: entry.latest_job.created_seq, reverse=True)
        return tuple(entries)

    def list_entries(
        self, *, limit: int = 20, before: int | None = None,
    ) -> tuple[tuple[LibraryEntry, ...], int | None]:
        if type(limit) is not int or not 1 <= limit <= 50:
            raise ValueError("limit must be between 1 and 50")
        if before is not None and (type(before) is not int or before <= 0):
            raise ValueError("before must be a positive integer")
        entries = self._entries()
        if before is not None:
            entries = tuple(
                entry for entry in entries if entry.latest_job.created_seq < before
            )
        page = entries[:limit]
        next_before = (
            page[-1].latest_job.created_seq
            if len(entries) > limit and page else None
        )
        return page, next_before

    def search(
        self, query: str, *, limit: int = 20,
    ) -> tuple[tuple[TranscriptSearchHit, ...], bool]:
        if not isinstance(query, str):
            raise TypeError("query must be text")
        normalized = query.strip().casefold()
        if not 2 <= len(normalized) <= 200:
            raise ValueError("query must contain between 2 and 200 characters")
        if type(limit) is not int or not 1 <= limit <= 50:
            raise ValueError("limit must be between 1 and 50")

        hits: list[TranscriptSearchHit] = []
        for entry in self._entries():
            job = entry.latest_job
            for segment in job.transcript.segments:
                if normalized in segment.text.casefold():
                    hits.append(TranscriptSearchHit(job, segment))
                    if len(hits) > limit:
                        return tuple(hits[:limit]), True
        return tuple(hits), False
