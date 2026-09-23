"""Offline migration contracts for the local job journal."""

import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from signaltranscript.backend.jobs import SCHEMA_VERSION, SQLiteJobs


class JobSchemaMigrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "jobs.db"

    def test_initialization_sets_explicit_schema_version(self):
        SQLiteJobs(self.path).initialize()
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)
            columns = {row[1] for row in db.execute("PRAGMA table_info(jobs)")}
        self.assertIn("evidence_json", columns)

    def test_legacy_unversioned_jobs_table_is_migrated_without_data_loss(self):
        transcript = json.dumps({
            "video_id": "legacy-video", "source": "manual_import", "language": "en",
            "provider": None, "model": None,
            "segments": [{"id": "s1", "text": "legacy", "start_ms": 0, "end_ms": 1000}],
        })
        with sqlite3.connect(self.path) as db:
            db.execute("""CREATE TABLE jobs (
                id TEXT PRIMARY KEY, state TEXT NOT NULL, transcript_json TEXT NOT NULL,
                provider TEXT NOT NULL, model TEXT NOT NULL, revision TEXT NOT NULL,
                max_chars INTEGER NOT NULL, section_count INTEGER NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0, error_code TEXT)""")
            db.execute("""INSERT INTO jobs
                (id,state,transcript_json,provider,model,revision,max_chars,section_count)
                VALUES ('legacy','QUEUED',?,'fake','model','v1',12000,1)""", (transcript,))

        jobs = SQLiteJobs(self.path)
        jobs.initialize()
        restored = jobs.get("legacy")
        self.assertIsNotNone(restored)
        self.assertEqual(restored.transcript.video_id, "legacy-video")
        self.assertIsNone(restored.evidence)
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)
            columns = {row[1] for row in db.execute("PRAGMA table_info(jobs)")}
        self.assertIn("evidence_json", columns)

    def test_newer_database_is_rejected_without_downgrade(self):
        future = SCHEMA_VERSION + 1
        with sqlite3.connect(self.path) as db:
            db.execute(f"PRAGMA user_version={future}")
            db.execute("CREATE TABLE future_marker (value TEXT NOT NULL)")
            db.execute("INSERT INTO future_marker VALUES ('keep')")

        with self.assertRaisesRegex(RuntimeError, "DATABASE_SCHEMA_NEWER_THAN_RUNTIME"):
            SQLiteJobs(self.path).initialize()

        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], future)
            self.assertEqual(db.execute("SELECT value FROM future_marker").fetchone()[0], "keep")
            self.assertIsNone(db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='jobs'"
            ).fetchone())

    def test_partial_legacy_schema_is_rejected_before_mutation(self):
        with sqlite3.connect(self.path) as db:
            db.execute("CREATE TABLE jobs (id TEXT PRIMARY KEY, state TEXT NOT NULL)")
            db.execute("INSERT INTO jobs VALUES ('legacy', 'QUEUED')")

        with self.assertRaisesRegex(RuntimeError, "DATABASE_SCHEMA_INCOMPATIBLE"):
            SQLiteJobs(self.path).initialize()

        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 0)
            self.assertEqual(
                {row[1] for row in db.execute("PRAGMA table_info(jobs)")},
                {"id", "state"},
            )
            self.assertEqual(db.execute("SELECT * FROM jobs").fetchone(), ("legacy", "QUEUED"))

    def test_unknown_legacy_columns_are_rejected_without_adoption(self):
        with sqlite3.connect(self.path) as db:
            db.execute("""CREATE TABLE jobs (
                id TEXT PRIMARY KEY, state TEXT NOT NULL, transcript_json TEXT NOT NULL,
                provider TEXT NOT NULL, model TEXT NOT NULL, revision TEXT NOT NULL,
                max_chars INTEGER NOT NULL, section_count INTEGER NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0, error_code TEXT,
                future_semantics TEXT NOT NULL DEFAULT 'keep')""")

        with self.assertRaisesRegex(RuntimeError, "DATABASE_SCHEMA_INCOMPATIBLE"):
            SQLiteJobs(self.path).initialize()

        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 0)
            columns = {row[1] for row in db.execute("PRAGMA table_info(jobs)")}
        self.assertIn("future_semantics", columns)
        self.assertNotIn("evidence_json", columns)


if __name__ == "__main__":
    unittest.main()
