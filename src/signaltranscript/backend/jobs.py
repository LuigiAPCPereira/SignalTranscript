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
from signaltranscript.backend.caption_evidence import CaptionEvidence, parse_manifest

STATES = frozenset({"QUEUED", "RUNNING", "INTERRUPTED", "FAILED", "WAITING_RATE_LIMIT", "COMPLETED", "CANCELLED"})
SCHEMA_VERSION = 3
_JOB_REQUIRED_COLUMNS = frozenset({
    "id", "state", "transcript_json", "provider", "model", "revision",
    "max_chars", "section_count", "attempts", "error_code",
})
_JOB_CURRENT_COLUMNS = _JOB_REQUIRED_COLUMNS | {"evidence_json", "created_seq"}


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
    created_seq: int
    evidence: CaptionEvidence | None = None


def safe_code(code: object) -> str:
    return code if isinstance(code, str) and re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", code) else "PROVIDER_FAILURE"


def _transcript(raw: str) -> Transcript:
    data = json.loads(raw)
    return Transcript(
        video_id=data["video_id"], source=data["source"],
        segments=tuple(Segment(**segment) for segment in data["segments"]),
        language=data.get("language"), provider=data.get("provider"), model=data.get("model"),
    )


def _import_payload(transcript: Transcript) -> dict[str, object]:
    return {
        "video_id": transcript.video_id,
        "source": transcript.source,
        "language": transcript.language,
        "segments": [asdict(segment) for segment in transcript.segments],
    }


def _evidence(raw: str | None, transcript: Transcript) -> CaptionEvidence | None:
    if raw is None:
        return None
    return parse_manifest(
        json.loads(raw), _import_payload(transcript), allow_verified_timeline=True,
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
        """Create or migrate the local job schema without accepting unknown futures."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self._db() as db:
                # Validate the database before changing journal mode, schema, or
                # user_version. A damaged journal must never be "migrated" into a
                # shape that appears current and recoverable.
                integrity = db.execute("PRAGMA integrity_check").fetchall()
                if integrity != [("ok",)]:
                    raise RuntimeError("DATABASE_INTEGRITY_FAILED")

                db.execute("PRAGMA journal_mode=WAL")
                version = db.execute("PRAGMA user_version").fetchone()[0]
                if version > SCHEMA_VERSION:
                    raise RuntimeError("DATABASE_SCHEMA_NEWER_THAN_RUNTIME")

                table_exists = db.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='jobs'"
                ).fetchone() is not None
                if table_exists:
                    columns = {row[1] for row in db.execute("PRAGMA table_info(jobs)")}
                    # Version 0 predates explicit migrations, but it is only safe to
                    # adopt a database whose known journal shape is complete. Refuse
                    # incompatible/partial schemas before ALTER or user_version writes.
                    if not _JOB_REQUIRED_COLUMNS.issubset(columns):
                        raise RuntimeError("DATABASE_SCHEMA_INCOMPATIBLE")
                    if not columns.issubset(_JOB_CURRENT_COLUMNS):
                        raise RuntimeError("DATABASE_SCHEMA_INCOMPATIBLE")

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
                    error_code TEXT,
                    evidence_json TEXT,
                    created_seq INTEGER NOT NULL)""")
                columns = {row[1] for row in db.execute("PRAGMA table_info(jobs)")}
                if "evidence_json" not in columns:
                    db.execute("ALTER TABLE jobs ADD COLUMN evidence_json TEXT")
                if "created_seq" not in columns:
                    db.execute("ALTER TABLE jobs ADD COLUMN created_seq INTEGER NOT NULL DEFAULT 0")

                # Persist a stable insertion sequence once. rowid is used only as a
                # one-time migration ordering for legacy rows; API/worker contracts
                # never expose or depend on rowid afterwards.
                max_seq = db.execute(
                    "SELECT COALESCE(MAX(created_seq), 0) FROM jobs"
                ).fetchone()[0]
                legacy = db.execute(
                    "SELECT rowid,id FROM jobs WHERE created_seq=0 ORDER BY rowid"
                ).fetchall()
                for _, legacy_id in legacy:
                    max_seq += 1
                    db.execute(
                        "UPDATE jobs SET created_seq=? WHERE id=?",
                        (max_seq, legacy_id),
                    )
                db.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_jobs_created_seq ON jobs(created_seq)"
                )
                # Historical databases predate user_version. Structural migrations
                # above are idempotent, so older compatible journals upgrade safely.
                db.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
        except sqlite3.DatabaseError as exc:
            # Do not expose SQLite's raw message or paths through callers. The
            # original database is left in place for explicit recovery/backup.
            raise RuntimeError("DATABASE_INTEGRITY_FAILED") from exc

    def recover_interrupted(self) -> None:
        """Only call while holding the exclusive process lock."""
        with self._db() as db:
            db.execute("UPDATE jobs SET state='INTERRUPTED', error_code='REMOTE_OUTCOME_UNKNOWN' "
                       "WHERE state='RUNNING'")

    def enqueue(self, transcript: Transcript, *, provider: str, model: str,
                revision: str, max_chars: int, evidence: CaptionEvidence | None = None) -> Job:
        for value in (provider, model, revision):
            if not isinstance(value, str) or not value.strip() or len(value) > 256:
                raise ValueError("invalid analysis identity")
        if len(transcript.segments) > 20_000:
            raise ValueError("transcript exceeds local upload limits")
        payload = json.dumps(asdict(transcript), ensure_ascii=False, separators=(",", ":"))
        if len(payload.encode("utf-8")) > 2_000_000:
            raise ValueError("transcript exceeds local upload limits")
        evidence_json = None
        if evidence is not None:
            validated = parse_manifest(
                asdict(evidence), _import_payload(transcript),
                allow_verified_timeline=evidence.timeline_match_status == "VERIFIED",
            )
            evidence_json = json.dumps(asdict(validated), ensure_ascii=False,
                                       sort_keys=True, separators=(",", ":"))
        sections = plan_sections(transcript, max_chars=max_chars)
        job_id = uuid4().hex
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            created_seq = db.execute(
                "SELECT COALESCE(MAX(created_seq), 0) + 1 FROM jobs"
            ).fetchone()[0]
            db.execute("""INSERT INTO jobs
                (id,state,transcript_json,provider,model,revision,max_chars,section_count,
                 evidence_json,created_seq)
                VALUES (?, 'QUEUED', ?, ?, ?, ?, ?, ?, ?, ?)""",
                (job_id, payload, provider, model, revision, max_chars, len(sections),
                 evidence_json, created_seq))
        return self.get(job_id)  # type: ignore[return-value]

    @staticmethod
    def _job(row: tuple[object, ...]) -> Job:
        transcript = _transcript(row[2])
        return Job(
            id=row[0], state=row[1], transcript=transcript,
            provider=row[3], model=row[4], revision=row[5], max_chars=row[6],
            section_count=row[7], attempts=row[8], error_code=row[9],
            created_seq=row[11], evidence=_evidence(row[10], transcript),
        )

    def get(self, job_id: str) -> Job | None:
        with self._db() as db:
            row = db.execute("""SELECT id,state,transcript_json,provider,model,revision,
                max_chars,section_count,attempts,error_code,evidence_json,created_seq
                FROM jobs WHERE id=?""", (job_id,)).fetchone()
        return None if row is None else self._job(row)

    def list_jobs(self, *, limit: int = 20, before: int | None = None) -> tuple[tuple[Job, ...], int | None]:
        """Newest-first stable local pagination by persisted insertion sequence."""
        if type(limit) is not int or not 1 <= limit <= 50:
            raise ValueError("limit must be between 1 and 50")
        if before is not None and (type(before) is not int or before <= 0):
            raise ValueError("before must be a positive integer")
        params: list[object] = []
        where = ""
        if before is not None:
            where = "WHERE created_seq < ?"
            params.append(before)
        params.append(limit + 1)
        with self._db() as db:
            rows = db.execute(f"""SELECT id,state,transcript_json,provider,model,revision,
                max_chars,section_count,attempts,error_code,evidence_json,created_seq
                FROM jobs {where} ORDER BY created_seq DESC LIMIT ?""", params).fetchall()
        page_rows = rows[:limit]
        next_before = page_rows[-1][11] if len(rows) > limit and page_rows else None
        return tuple(self._job(row) for row in page_rows), next_before

    def artifact_presence(self, job_id: str) -> tuple[bool, bool]:
        """Presence hints only; artifact endpoints perform integrity validation."""
        with self._db() as db:
            sections_table = db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='analysis_sections'"
            ).fetchone() is not None
            synthesis_table = db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='global_syntheses'"
            ).fetchone() is not None
            sections_present = bool(sections_table and db.execute(
                "SELECT 1 FROM analysis_sections WHERE run_id=? LIMIT 1", (job_id,)
            ).fetchone())
            synthesis_present = bool(synthesis_table and db.execute(
                "SELECT 1 FROM global_syntheses WHERE run_id=? LIMIT 1", (job_id,)
            ).fetchone())
        return sections_present, synthesis_present

    def completed_sections(self, job_id: str) -> int:
        with self._db() as db:
            table = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='analysis_sections'").fetchone()
            if not table:
                return 0
            return db.execute("SELECT count(*) FROM analysis_sections WHERE run_id=?", (job_id,)).fetchone()[0]

    def claim_next(self) -> Job | None:
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM jobs WHERE state='RUNNING' LIMIT 1").fetchone():
                return None
            row = db.execute(
                "SELECT id FROM jobs WHERE state='QUEUED' ORDER BY created_seq LIMIT 1"
            ).fetchone()
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

    def cancel(self, job_id: str) -> Job:
        """Cancel only work that is known not to be executing remotely.

        RUNNING is deliberately rejected: the local journal cannot prove that a
        provider request was cancelled, so it must not publish a false terminal
        cancellation state for in-flight work.
        """
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT state FROM jobs WHERE id=?", (job_id,)).fetchone()
            if row is None:
                raise KeyError(job_id)
            state = row[0]
            if state == "RUNNING":
                raise JobConflict("REMOTE_CANCELLATION_UNCONFIRMED")
            if state not in {"QUEUED", "INTERRUPTED", "FAILED", "WAITING_RATE_LIMIT"}:
                raise JobConflict("JOB_NOT_CANCELLABLE")
            db.execute("UPDATE jobs SET state='CANCELLED',error_code=NULL WHERE id=?", (job_id,))
        return self.get(job_id)  # type: ignore[return-value]

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
