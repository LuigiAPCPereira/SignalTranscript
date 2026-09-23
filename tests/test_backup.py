import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from signaltranscript.backend.backup import BackupError, backup_sqlite, main


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

    def test_publication_race_never_overwrites_destination_or_leaves_temp(self):
        target = self.root / "raced.db"
        real_link = os.link

        def destination_appears(source, destination):
            Path(destination).write_bytes(b"competitor")
            return real_link(source, destination)

        with patch("signaltranscript.backend.backup.os.link", side_effect=destination_appears):
            with self.assertRaisesRegex(BackupError, "DESTINATION_EXISTS"):
                backup_sqlite(self.source, target)
        self.assertEqual(target.read_bytes(), b"competitor")
        self.assertEqual(list(self.root.glob(f".{target.name}.*.tmp")), [])

    def test_failed_snapshot_is_never_published_and_temp_is_removed(self):
        target = self.root / "failed.db"
        with patch("sqlite3.Connection.backup", side_effect=sqlite3.DatabaseError("boom")):
            with self.assertRaisesRegex(BackupError, "SQLITE_BACKUP_FAILED"):
                backup_sqlite(self.source, target)
        self.assertFalse(target.exists())
        self.assertEqual(list(self.root.glob(f".{target.name}.*.tmp")), [])

    def test_cli_requires_explicit_paths_and_creates_snapshot(self):
        target = self.root / "cli.backup.db"
        self.assertEqual(main(["--source", str(self.source), "--destination", str(target)]), 0)
        with sqlite3.connect(target) as db:
            self.assertEqual(db.execute("SELECT value FROM sample").fetchone()[0], "checkpoint")

    def test_cli_failure_is_sanitized_and_does_not_overwrite(self):
        target = self.root / "existing.db"
        target.write_text("keep", encoding="utf-8")
        with patch("sys.stderr") as stderr, self.assertRaises(SystemExit) as raised:
            main(["--source", str(self.source), "--destination", str(target)])
        self.assertEqual(raised.exception.code, 2)
        rendered = "".join(str(call) for call in stderr.write.call_args_list)
        self.assertIn("backup could not be created safely", rendered)
        self.assertNotIn(str(self.source), rendered)
        self.assertNotIn(str(target), rendered)
        self.assertEqual(target.read_text(encoding="utf-8"), "keep")


if __name__ == "__main__":
    unittest.main()
