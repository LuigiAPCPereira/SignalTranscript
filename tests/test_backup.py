import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

from signaltranscript.backend.backup import BackupError, backup_sqlite


class SQLiteBackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "jobs.db"
        with sqlite3.connect(self.source) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
            db.execute("INSERT INTO sample(value) VALUES ('checkpoint')")

    def test_backup_is_consistent_private_and_independent(self):
        target = self.root / "jobs.backup.db"
        result = backup_sqlite(self.source, target)
        self.assertEqual(result, target)
        self.assertEqual(os.stat(target).st_mode & 0o777, 0o600)
        with sqlite3.connect(target) as db:
            self.assertEqual(db.execute("SELECT value FROM sample").fetchone()[0], "checkpoint")
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        with sqlite3.connect(self.source) as db:
            db.execute("INSERT INTO sample(value) VALUES ('later')")
        with sqlite3.connect(target) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM sample").fetchone()[0], 1)

    def test_refuses_overwrite_same_path_and_missing_parent(self):
        existing = self.root / "existing.db"
        existing.write_bytes(b"keep")
        cases = (self.source, existing, self.root / "missing" / "backup.db")
        for target in cases:
            with self.subTest(target=target), self.assertRaises(BackupError):
                backup_sqlite(self.source, target)
        self.assertEqual(existing.read_bytes(), b"keep")

    def test_rejects_non_database_without_leaving_destination(self):
        bad = self.root / "not-sqlite.db"
        bad.write_text("not sqlite", encoding="utf-8")
        target = self.root / "bad.backup.db"
        with self.assertRaises(BackupError):
            backup_sqlite(bad, target)
        self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
