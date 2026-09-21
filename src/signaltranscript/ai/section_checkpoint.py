"""Durable SQLite checkpoints for section analysis, independent of AI providers.

One local worker owns an active run. This is not a job lease, full worker, or
exactly-once remote execution guarantee. No transaction spans an API call.
"""

from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from typing import Iterator

from signaltranscript.ai.long_form import (
    AnalyzedSection, SectionedAnalysis, _analyze_planned,
    compact_source_chars, plan_sections,
)
from signaltranscript.ai.ports import Analysis, AnalysisProvider, Idea, Transcript, validate_analysis


class CheckpointMismatch(ValueError):
    """Previously saved data cannot safely be reused for this run."""


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _fingerprint(transcript: Transcript, planned: tuple[Transcript, ...]) -> str:
    payload = {
        "checkpoint_schema": 1,
        "transcript": asdict(transcript),
        "section_ids": [[segment.id for segment in part.segments] for part in planned],
    }
    return sha256(_json(payload).encode("utf-8")).hexdigest()


def _payload(section: AnalyzedSection) -> str:
    return _json(asdict(section))


def _restore(raw: str) -> AnalyzedSection:
    try:
        data = json.loads(raw)
        if not isinstance(data, dict) or set(data) != {"index", "segment_ids", "analysis"}:
            raise ValueError
        analysis = data["analysis"]
        if not isinstance(analysis, dict) or set(analysis) != {"summary", "ideas", "provider", "model"}:
            raise ValueError
        if type(data["index"]) is not int or not isinstance(data["segment_ids"], list):
            raise ValueError
        if not all(isinstance(x, str) for x in data["segment_ids"]):
            raise ValueError
        if not all(isinstance(analysis[key], str) for key in ("summary", "provider", "model")):
            raise ValueError
        if not isinstance(analysis["ideas"], list):
            raise ValueError
        ideas = []
        for item in analysis["ideas"]:
            if not isinstance(item, dict) or set(item) != {"title", "explanation", "source_segment_ids"}:
                raise ValueError
            if (not isinstance(item["title"], str) or not isinstance(item["explanation"], str)
                    or not isinstance(item["source_segment_ids"], list)
                    or not all(isinstance(x, str) for x in item["source_segment_ids"])):
                raise ValueError
            ideas.append(Idea(item["title"], item["explanation"], tuple(item["source_segment_ids"])))
        return AnalyzedSection(
            data["index"], tuple(data["segment_ids"]),
            Analysis(analysis["summary"], tuple(ideas), analysis["provider"], analysis["model"]),
        )
    except (TypeError, ValueError, KeyError) as exc:
        raise CheckpointMismatch("INVALID_CHECKPOINT_PAYLOAD") from exc


class SQLiteSectionCheckpoint:
    """Bind run ID to immutable input, plan, provider/model and analysis revision.

    The caller MUST change revision when prompts, schema, or analysis settings
    change. The provider/model are explicit, never inferred from a prior run.
    """

    def __init__(self, path: Path, *, run_id: str, transcript: Transcript,
                 provider: str, model: str, revision: str, max_chars: int,
                 measure: Callable[[Transcript], int] = compact_source_chars,
                 max_sections: int = 64) -> None:
        for name, value in (("run_id", run_id), ("provider", provider),
                            ("model", model), ("revision", revision)):
            if not isinstance(value, str) or not value.strip() or len(value) > 256:
                raise ValueError(f"{name} must be nonempty and at most 256 characters")
        self.path = Path(path)
        self.run_id = run_id
        self.provider = provider
        self.model = model
        self.revision = revision
        # Preflight before any DB write or remote call.
        self.planned = plan_sections(transcript, max_chars=max_chars,
                                     measure=measure, max_sections=max_sections)
        self.fingerprint = _fingerprint(transcript, self.planned)
        self.video_id = transcript.video_id

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=5)
        try:
            conn.execute("PRAGMA foreign_keys=ON")
            with conn:
                yield conn
        finally:
            conn.close()

    def _schema(self, conn: sqlite3.Connection) -> None:
        conn.execute("""CREATE TABLE IF NOT EXISTS analysis_runs (
            run_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL,
            provider TEXT NOT NULL, model TEXT NOT NULL, revision TEXT NOT NULL,
            section_count INTEGER NOT NULL)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS analysis_sections (
            run_id TEXT NOT NULL REFERENCES analysis_runs(run_id),
            section_index INTEGER NOT NULL, payload TEXT NOT NULL,
            PRIMARY KEY (run_id, section_index))""")

    def _assert_run(self, conn: sqlite3.Connection) -> None:
        row = conn.execute("""SELECT fingerprint, provider, model, revision, section_count
                              FROM analysis_runs WHERE run_id=?""", (self.run_id,)).fetchone()
        expected = (self.fingerprint, self.provider, self.model,
                    self.revision, len(self.planned))
        if row != expected:
            raise CheckpointMismatch("RUN_CONFIGURATION_CHANGED")

    def _loaded(self, conn: sqlite3.Connection) -> tuple[AnalyzedSection, ...]:
        rows = conn.execute("""SELECT section_index, payload FROM analysis_sections
                               WHERE run_id=? ORDER BY section_index""", (self.run_id,)).fetchall()
        items: list[AnalyzedSection] = []
        for expected_index, (index, raw) in enumerate(rows):
            if index != expected_index or index >= len(self.planned):
                raise CheckpointMismatch("NONCONTIGUOUS_CHECKPOINT")
            section = _restore(raw)
            part = self.planned[index]
            if section.index != index or section.segment_ids != tuple(seg.id for seg in part.segments):
                raise CheckpointMismatch("SECTION_PLAN_CHANGED")
            if (section.analysis.provider, section.analysis.model) != (self.provider, self.model):
                raise CheckpointMismatch("PROVIDER_CHANGED")
            try:
                validate_analysis(part, section.analysis)
            except ValueError as exc:
                raise CheckpointMismatch("INVALID_CHECKPOINT_EVIDENCE") from exc
            items.append(section)
        return tuple(items)

    def open_and_load(self) -> tuple[AnalyzedSection, ...]:
        """Create/reopen run and reject all stale or corrupted stored sections."""
        with self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._schema(conn)
            conn.execute("""INSERT OR IGNORE INTO analysis_runs
                (run_id, fingerprint, provider, model, revision, section_count)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (self.run_id, self.fingerprint, self.provider, self.model,
                 self.revision, len(self.planned)))
            self._assert_run(conn)
            return self._loaded(conn)

    def save(self, section: AnalyzedSection) -> None:
        """Commit one validated section; replay of identical data is idempotent."""
        if type(section.index) is not int or not 0 <= section.index < len(self.planned):
            raise CheckpointMismatch("INVALID_SECTION_INDEX")
        part = self.planned[section.index]
        if section.segment_ids != tuple(seg.id for seg in part.segments):
            raise CheckpointMismatch("SECTION_PLAN_CHANGED")
        if (section.analysis.provider, section.analysis.model) != (self.provider, self.model):
            raise CheckpointMismatch("PROVIDER_CHANGED")
        try:
            validate_analysis(part, section.analysis)
        except ValueError as exc:
            raise CheckpointMismatch("INVALID_CHECKPOINT_EVIDENCE") from exc
        payload = _payload(section)
        with self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._assert_run(conn)
            existing = self._loaded(conn)
            if section.index < len(existing):
                old = conn.execute("""SELECT payload FROM analysis_sections
                                      WHERE run_id=? AND section_index=?""",
                                   (self.run_id, section.index)).fetchone()[0]
                if old != payload:
                    raise CheckpointMismatch("CHECKPOINT_REWRITE_FORBIDDEN")
                return
            if section.index != len(existing):
                raise CheckpointMismatch("CHECKPOINT_OUT_OF_ORDER")
            conn.execute("""INSERT INTO analysis_sections (run_id, section_index, payload)
                            VALUES (?, ?, ?)""", (self.run_id, section.index, payload))


async def analyze_with_checkpoint(
    checkpoint: SQLiteSectionCheckpoint, provider: AnalysisProvider,
) -> SectionedAnalysis:
    """Resume a validated prefix. Unknown remote outcomes stay uncommitted."""
    previous = checkpoint.open_and_load()

    async def persist(section: AnalyzedSection) -> None:
        checkpoint.save(section)

    return await _analyze_planned(checkpoint.video_id, checkpoint.planned, provider,
                                  previous=previous, on_section_complete=persist)
