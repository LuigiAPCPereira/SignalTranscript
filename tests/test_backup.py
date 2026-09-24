from hashlib import sha256
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from signaltranscript.backend.backup import (
    BackupError,
    backup_sqlite,
    main,
    restore_sqlite_backup,
    verify_sqlite_backup,
)


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

    def test_verify_accepts_snapshot_without_modifying_it(self):
        target = self.root / "verified.db"
        backup_sqlite(self.source, target)
        before = target.read_bytes()
        self.assertEqual(verify_sqlite_backup(target), target)
        self.assertEqual(target.read_bytes(), before)

    def test_verify_can_pin_exact_snapshot_hash(self):
        target = self.root / "pinned.db"
        backup_sqlite(self.source, target)
        expected = sha256(target.read_bytes()).hexdigest()
        self.assertEqual(verify_sqlite_backup(target, expected_sha256=expected.upper()), target)
        with self.assertRaisesRegex(BackupError, "SNAPSHOT_HASH_MISMATCH"):
            verify_sqlite_backup(target, expected_sha256="0" * 64)
        with self.assertRaisesRegex(BackupError, "EXPECTED_SHA256_INVALID"):
            verify_sqlite_backup(target, expected_sha256="not-a-digest")

    def test_verify_rejects_invalid_file_and_symlink(self):
        invalid = self.root / "invalid.db"
        invalid.write_bytes(b"not sqlite")
        with self.assertRaisesRegex(BackupError, "SQLITE_VERIFICATION_FAILED"):
            verify_sqlite_backup(invalid)
        link = self.root / "linked.db"
        link.symlink_to(self.source)
        with self.assertRaisesRegex(BackupError, "SOURCE_NOT_REGULAR_FILE"):
            verify_sqlite_backup(link)

    def test_restore_stages_verified_snapshot_without_touching_active_database(self):
        snapshot = self.root / "snapshot.db"
        backup_sqlite(self.source, snapshot)
        active_before = self.source.read_bytes()
        restored = self.root / "restored.db"
        self.assertEqual(restore_sqlite_backup(snapshot, restored), restored)
        self.assertEqual(self.source.read_bytes(), active_before)
        self.assertEqual(os.stat(restored).st_mode & 0o777, 0o600)
        with sqlite3.connect(restored) as db:
            self.assertEqual(db.execute("SELECT value FROM sample").fetchone()[0], "checkpoint")
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")

    def test_restore_can_require_exact_snapshot_hash(self):
        snapshot = self.root / "restore-pinned.db"
        backup_sqlite(self.source, snapshot)
        expected = sha256(snapshot.read_bytes()).hexdigest()
        restored = self.root / "restore-pinned-output.db"
        self.assertEqual(
            restore_sqlite_backup(snapshot, restored, expected_sha256=expected), restored
        )
        wrong_destination = self.root / "wrong-hash-output.db"
        with self.assertRaisesRegex(BackupError, "SNAPSHOT_HASH_MISMATCH"):
            restore_sqlite_backup(
                snapshot, wrong_destination, expected_sha256="f" * 64
            )
        self.assertFalse(wrong_destination.exists())

    def test_restore_refuses_overwrite_same_path_invalid_snapshot_and_symlink(self):
        snapshot = self.root / "snapshot.db"
        backup_sqlite(self.source, snapshot)
        existing = self.root / "active.db"
        existing.write_bytes(b"keep")
        with self.assertRaisesRegex(BackupError, "DESTINATION_EXISTS"):
            restore_sqlite_backup(snapshot, existing)
        self.assertEqual(existing.read_bytes(), b"keep")
        with self.assertRaisesRegex(BackupError, "DESTINATION_EQUALS_SOURCE"):
            restore_sqlite_backup(snapshot, snapshot)
        invalid = self.root / "invalid-restore.db"
        invalid.write_bytes(b"not sqlite")
        with self.assertRaisesRegex(BackupError, "SQLITE_VERIFICATION_FAILED"):
            restore_sqlite_backup(invalid, self.root / "never.db")
        link = self.root / "snapshot-link.db"
        link.symlink_to(snapshot)
        with self.assertRaisesRegex(BackupError, "SOURCE_NOT_REGULAR_FILE"):
            restore_sqlite_backup(link, self.root / "never-link.db")

    def test_cli_requires_explicit_paths_and_creates_snapshot(self):
        target = self.root / "cli.backup.db"
        self.assertEqual(main(["--source", str(self.source), "--destination", str(target)]), 0)
        with sqlite3.connect(target) as db:
            self.assertEqual(db.execute("SELECT value FROM sample").fetchone()[0], "checkpoint")

    def test_cli_can_verify_snapshot_read_only(self):
        target = self.root / "cli.verify.db"
        backup_sqlite(self.source, target)
        before = target.read_bytes()
        self.assertEqual(main(["--verify", str(target)]), 0)
        self.assertEqual(target.read_bytes(), before)

    def test_cli_can_verify_and_restore_with_pinned_hash(self):
        snapshot = self.root / "cli.pinned.db"
        backup_sqlite(self.source, snapshot)
        expected = sha256(snapshot.read_bytes()).hexdigest()
        self.assertEqual(
            main(["--verify", str(snapshot), "--expect-sha256", expected]), 0
        )
        restored = self.root / "cli.pinned.restored.db"
        self.assertEqual(
            main([
                "--restore", str(snapshot), "--destination", str(restored),
                "--expect-sha256", expected,
            ]),
            0,
        )
        with sqlite3.connect(restored) as db:
            self.assertEqual(db.execute("SELECT value FROM sample").fetchone()[0], "checkpoint")

    def test_cli_can_stage_restore_to_new_path(self):
        snapshot = self.root / "cli.snapshot.db"
        backup_sqlite(self.source, snapshot)
        restored = self.root / "cli.restored.db"
        self.assertEqual(main(["--restore", str(snapshot), "--destination", str(restored)]), 0)
        with sqlite3.connect(restored) as db:
            self.assertEqual(db.execute("SELECT value FROM sample").fetchone()[0], "checkpoint")

    def test_cli_rejects_ambiguous_modes(self):
        target = self.root / "ambiguous.db"
        cases = (
            ["--source", str(self.source), "--destination", str(target), "--verify", str(self.source)],
            ["--source", str(self.source), "--destination", str(target), "--restore", str(self.source)],
            ["--verify", str(self.source), "--destination", str(target)],
            ["--source", str(self.source), "--destination", str(target), "--expect-sha256", "0" * 64],
        )
        for argv in cases:
            with self.subTest(argv=argv), patch("sys.stderr"), self.assertRaises(SystemExit) as raised:
                main(argv)
            self.assertEqual(raised.exception.code, 2)
            self.assertFalse(target.exists())

    def test_cli_failure_is_sanitized_and_does_not_overwrite(self):
        target = self.root / "existing.db"
        target.write_text("keep", encoding="utf-8")
        with patch("sys.stderr") as stderr, self.assertRaises(SystemExit) as raised:
            main(["--source", str(self.source), "--destination", str(target)])
        self.assertEqual(raised.exception.code, 2)
        rendered = "".join(str(call) for call in stderr.write.call_args_list)
        self.assertIn("backup operation could not be completed safely", rendered)
        self.assertNotIn(str(self.source), rendered)
        self.assertNotIn(str(target), rendered)
        self.assertEqual(target.read_text(encoding="utf-8"), "keep")


if __name__ == "__main__":
    unittest.main()
