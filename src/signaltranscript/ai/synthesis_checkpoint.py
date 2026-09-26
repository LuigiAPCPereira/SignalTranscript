"""Versioned SQLite checkpoints for validated global synthesis results.

A checkpoint is written only after an explicit synthesis call returned and passed
all transcript/evidence validation. Unknown remote outcomes remain uncommitted.
The caller must change ``revision`` whenever synthesis prompt/schema/settings
change; provider selection and retries stay outside this module.
"""

from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

from signaltranscript.ai.coverage import assess_reference_positions
from signaltranscript.ai.long_form import SectionedAnalysis
from signaltranscript.ai.ports import Analysis, Idea, Transcript, validate_analysis
from signaltranscript.ai.synthesis import (
    GlobalSynthesis, GlobalSynthesisProvider, SynthesisValidationError,
    synthesize_global,
)


SCHEMA_VERSION = 1


class SynthesisCheckpointMismatch(ValueError):
    """Stored synthesis cannot safely be reused for this configuration."""


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _fingerprint(transcript: Transcript, sectioned: SectionedAnalysis) -> str:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "transcript": asdict(transcript),
        "section_ids": [list(section.segment_ids) for section in sectioned.sections],
    }
    return sha256(_json(payload).encode("utf-8")).hexdigest()


def _analysis_payload(analysis: Analysis) -> str:
    return _json(asdict(analysis))


def _restore_analysis(raw: str) -> Analysis:
    try:
        data = json.loads(raw)
        if not isinstance(data, dict) or set(data) != {"summary", "ideas", "provider", "model"}:
            raise ValueError
        if not all(isinstance(data[key], str) for key in ("summary", "provider", "model")):
            raise ValueError
        if not isinstance(data["ideas"], list):
            raise ValueError
        ideas = []
        for item in data["ideas"]:
            if not isinstance(item, dict) or set(item) != {"title", "explanation", "source_segment_ids"}:
                raise ValueError
            if (not isinstance(item["title"], str)
                    or not isinstance(item["explanation"], str)
                    or not isinstance(item["source_segment_ids"], list)
                    or not all(isinstance(value, str) for value in item["source_segment_ids"])):
                raise ValueError
            ideas.append(Idea(item["title"], item["explanation"], tuple(item["source_segment_ids"])))
        return Analysis(data["summary"], tuple(ideas), data["provider"], data["model"])
    except (json.JSONDecodeError, TypeError, ValueError, KeyError) as exc:
        raise SynthesisCheckpointMismatch("INVALID_SYNTHESIS_PAYLOAD") from exc


class SQLiteGlobalSynthesisCheckpoint:
    """Bind one immutable global synthesis to transcript, sections and revision."""

    def __init__(self, path: Path, *, run_id: str, transcript: Transcript,
                 sectioned: SectionedAnalysis, provider: str, model: str,
                 revision: str) -> None:
        for name, value in (("run_id", run_id), ("provider", provider),
                            ("model", model), ("revision", revision)):
            if not isinstance(value, str) or not value.strip() or len(value) > 256:
                raise ValueError(f"{name} must be nonempty and at most 256 characters")
        if sectioned.video_id != transcript.video_id or not sectioned.complete:
            raise SynthesisCheckpointMismatch("SECTIONS_NOT_SYNTHESIZABLE")
        section_ids = tuple(section.segment_ids for section in sectioned.sections)
        try:
            assess_reference_positions(transcript, section_ids, ())
        except ValueError as exc:
            raise SynthesisCheckpointMismatch("SECTION_COVERAGE_MISMATCH") from exc
        self.path = Path(path)
        self.run_id = run_id
        self.transcript = transcript
        self.sectioned = sectioned
        self.provider = provider
        self.model = model
        self.revision = revision
        self.fingerprint = _fingerprint(transcript, sectioned)
        self.section_ids = section_ids

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=5)
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("""CREATE TABLE IF NOT EXISTS global_syntheses (
            run_id TEXT PRIMARY KEY,
            schema_version INTEGER NOT NULL,
            fingerprint TEXT NOT NULL,
            provider TEXT NOT NULL,
            model TEXT NOT NULL,
            revision TEXT NOT NULL,
            payload TEXT NOT NULL)""")
        return conn

    def _validate(self, analysis: Analysis) -> GlobalSynthesis:
        if (analysis.provider, analysis.model) != (self.provider, self.model):
            raise SynthesisCheckpointMismatch("PROVIDER_CHANGED")
        try:
            validate_analysis(self.transcript, analysis)
            references = (segment_id for idea in analysis.ideas for segment_id in idea.source_segment_ids)
            coverage = assess_reference_positions(self.transcript, self.section_ids, references)
        except (TypeError, ValueError) as exc:
            raise SynthesisCheckpointMismatch("INVALID_SYNTHESIS_EVIDENCE") from exc
        if len(self.transcript.segments) >= 3 and not coverage.spans_all_positions:
            raise SynthesisCheckpointMismatch("INSUFFICIENT_POSITIONAL_COVERAGE")
        return GlobalSynthesis(analysis, coverage)

    def _load_from(self, conn: sqlite3.Connection) -> GlobalSynthesis | None:
        row = conn.execute("""SELECT schema_version, fingerprint, provider, model,
                              revision, payload FROM global_syntheses WHERE run_id=?""",
                           (self.run_id,)).fetchone()
        if row is None:
            return None
        expected = (SCHEMA_VERSION, self.fingerprint, self.provider, self.model, self.revision)
        if row[:5] != expected:
            raise SynthesisCheckpointMismatch("RUN_CONFIGURATION_CHANGED")
        return self._validate(_restore_analysis(row[5]))

    def load(self) -> GlobalSynthesis | None:
        """Return a validated result, creating checkpoint schema when needed by writers."""
        conn = self._connect()
        try:
            return self._load_from(conn)
        finally:
            conn.close()

    def load_existing(self) -> GlobalSynthesis | None:
        """Read an already persisted result without DDL or provider calls."""
        conn = sqlite3.connect(self.path, timeout=5)
        try:
            table = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='global_syntheses'"
            ).fetchone()
            if table is None:
                return None
            return self._load_from(conn)
        finally:
            conn.close()

    def save(self, result: GlobalSynthesis) -> None:
        """Persist once; identical replay is idempotent and rewrite is forbidden."""
        validated = self._validate(result.analysis)
        payload = _analysis_payload(validated.analysis)
        conn = self._connect()
        try:
            with conn:
                existing = conn.execute("SELECT payload FROM global_syntheses WHERE run_id=?",
                                        (self.run_id,)).fetchone()
                if existing is not None:
                    if existing[0] != payload:
                        raise SynthesisCheckpointMismatch("SYNTHESIS_REWRITE_FORBIDDEN")
                    return
                conn.execute("""INSERT INTO global_syntheses
                    (run_id, schema_version, fingerprint, provider, model, revision, payload)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (self.run_id, SCHEMA_VERSION, self.fingerprint, self.provider,
                     self.model, self.revision, payload))
        finally:
            conn.close()


async def synthesize_with_checkpoint(
    checkpoint: SQLiteGlobalSynthesisCheckpoint,
    provider: GlobalSynthesisProvider,
) -> GlobalSynthesis:
    """Reuse a validated synthesis or make one explicit call and persist it."""
    previous = checkpoint.load()
    if previous is not None:
        return previous
    try:
        result = await synthesize_global(
            checkpoint.transcript, checkpoint.sectioned, provider,
        )
    except SynthesisValidationError:
        # No checkpoint is written for invalid or unknown provider outcomes.
        raise
    if (result.analysis.provider, result.analysis.model) != (checkpoint.provider, checkpoint.model):
        raise SynthesisCheckpointMismatch("PROVIDER_CHANGED")
    checkpoint.save(result)
    return result
