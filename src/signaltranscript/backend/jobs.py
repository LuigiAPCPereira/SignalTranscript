"""Single-process SQLite job journal for analysis of imported transcripts.

Provider choice is injected by the application; no automatic cost-bearing retry.
The external process lock belongs to the app lifespan (see api.py).
"""

from contextlib import contextmanager
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import sqlite3
from typing import Iterator
from uuid import uuid4

from signaltranscript.ai.long_form import plan_sections
from signaltranscript.ai.ports import Segment, Transcript

STATES = frozenset({"QUEUED", "RUNNING", "INTERRUPTED", "FAILED", "WAITING_RATE_LIMIT", "COMPLETED"})


class JobConflict(ValueError):
    """A requested transition or provider configuration is unsafe."""


@dataclass(frozen=True, slots=True)
class Job:
    id: str
    state: str
    transcript: Transcript
    provider: str
    model: str
    revision: str
    max_chars: int
    section_count: int
    attempts: int
    error_code: str | None


def safe_code(code: object) -> str:
    return code if isinstance(code, str) and re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", code) else "PROVIDER_FAILURE"


def _transcript(raw: str) -> Transcript:
    data = json.loads(raw)
    return Transcript(
        video_id=data["video_id"], source=data["source"],
        segments=tuple(Segment(**segment) for segment in data["segments"]),
        language=data.get("language"), provider=data.get("provider"), model=data.get("model"),
    )


class SQLiteJobs:
    """Short transactions; one active executor owns the database's process lock."""

    def __init__(self, path: Path):
        self.path = Path(path)

    @contextmanager
    def _db(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=5)
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._db() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("""CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                state TEXT NOT NULL,
                transcript_json TEXT NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                revision TEXT NOT NULL,
                max_chars INTEGER NOT NULL,
                section_count INTEGER NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                error_code TEXT)""")

    def recover_interrupted(self) -> None:
        """Only call while holding the exclusive process lock."""
        with self._db() as db:
            db.execute("UPDATE jobs SET state='INTERRUPTED', error_code='REMOTE_OUTCOME_UNKNOWN' "
                       "WHERE state='RUNNING'")

    def enqueue(self, transcript: Transcript, *, provider: str, model: str,
                revision: str, max_chars: int) -> Job:
        for value in (provider, model, revision):
            if not isinstance(value, str) or not value.strip() or len(value) > 256:
                raise ValueError("invalid analysis identity")
        if len(transcript.segments) > 20_000:
            raise ValueError("transcript exceeds local upload limits")
        payload = json.dumps(asdict(transcript), ensure_ascii=False, separators=(",", ":"))
        if len(payload.encode("utf-8")) > 2_000_000:
            raise ValueError("transcript exceeds local upload limits")
        sections = plan_sections(transcript, max_chars=max_chars)
        job_id = uuid4().hex
        with self._db() as db:
            db.execute("""INSERT INTO jobs
                (id,state,transcript_json,provider,model,revision,max_chars,section_count)
                VALUES (?, 'QUEUED', ?, ?, ?, ?, ?, ?)""",
                (job_id, payload, provider, model, revision, max_chars, len(sections)))
        return self.get(job_id)  # type: ignore[return-value]

    def get(self, job_id: str) -> Job | None:
        with self._db() as db:
            row = db.execute("""SELECT id,state,transcript_json,provider,model,revision,
                max_chars,section_count,attempts,error_code FROM jobs WHERE id=?""", (job_id,)).fetchone()
        return (Job(row[0], row[1], _transcript(row[2]), *row[3:]) if row else None)

    def completed_sections(self, job_id: str) -> int:
        with self._db() as db:
            table = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='analysis_sections'").fetchone()
            if not table:
                return 0
            return db.execute("SELECT count(*) FROM analysis_sections WHERE run_id=?", (job_id,)).fetchone()[0]

    def claim_next(self) -> Job | None:
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            # Enforce at most one RUNNING job in the single-process MVP.
            if db.execute("SELECT 1 FROM jobs WHERE state='RUNNING' LIMIT 1").fetchone():
                return None
            row = db.execute("SELECT id FROM jobs WHERE state='QUEUED' ORDER BY rowid LIMIT 1").fetchone()
            if row is None:
                return None
            db.execute("UPDATE jobs SET state='RUNNING', attempts=attempts+1,error_code=NULL WHERE id=?", row)
            job_id = row[0]
        return self.get(job_id)

    def finish(self, job_id: str, state: str, error: str | None = None) -> None:
        if state not in {"COMPLETED", "FAILED", "INTERRUPTED", "WAITING_RATE_LIMIT"}:
            raise ValueError("invalid terminal state")
        with self._db() as db:
            changed = db.execute("UPDATE jobs SET state=?,error_code=? WHERE id=? AND state='RUNNING'",
                                 (state, safe_code(error) if error else None, job_id)).rowcount
            if changed != 1:
                raise JobConflict("JOB_NOT_RUNNING")

    def resume(self, job_id: str, *, provider: str, model: str, revision: str,
               max_chars: int) -> Job:
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT state,provider,model,revision,max_chars FROM jobs WHERE id=?", (job_id,)).fetchone()
            if row is None:
                raise KeyError(job_id)
            if row[1:] != (provider, model, revision, max_chars):
                raise JobConflict("CONFIGURATION_CHANGED")
            if row[0] not in {"INTERRUPTED", "FAILED", "WAITING_RATE_LIMIT"}:
                raise JobConflict("JOB_NOT_RESUMABLE")
            db.execute("UPDATE jobs SET state='QUEUED',error_code=NULL WHERE id=?", (job_id,))
        return self.get(job_id)  # type: ignore[return-value]
