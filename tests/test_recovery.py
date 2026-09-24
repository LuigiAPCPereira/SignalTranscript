from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from signaltranscript.backend.backup import BackupError, backup_sqlite
from signaltranscript.backend.recovery import main, stage_verified_recovery


class SQLiteRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.active = self.root / "active.db"
        with sqlite3.connect(self.active) as db:
            db.execute("PRAGMA user_version = 2")
            db.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
            db.execute("INSERT INTO sample(value) VALUES ('checkpoint')")
        self.snapshot = self.root / "snapshot.db"
        backup_sqlite(self.active, self.snapshot)

    def test_stages_new_database_and_returns_verified_receipt(self):
        active_before = self.active.read_bytes()
        destination = self.root / "staged.db"

        receipt = stage_verified_recovery(self.snapshot, destination)

        self.assertTrue(destination.exists())
        self.assertEqual(self.active.read_bytes(), active_before)
        self.assertEqual(receipt.sqlite_user_version, 2)
        self.assertGreater(receipt.restored_size_bytes, 0)
        self.assertEqual(len(receipt.source_sha256), 64)
        self.assertEqual(len(receipt.restored_sha256), 64)
        with sqlite3.connect(destination) as db:
            self.assertEqual(db.execute("SELECT value FROM sample").fetchone()[0], "checkpoint")
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")

    def test_refuses_existing_destination_without_touching_it(self):
        destination = self.root / "existing.db"
        destination.write_bytes(b"keep")

        with self.assertRaisesRegex(BackupError, "DESTINATION_EXISTS"):
            stage_verified_recovery(self.snapshot, destination)

        self.assertEqual(destination.read_bytes(), b"keep")

    def test_source_is_pinned_between_inspection_and_restore(self):
        destination = self.root / "never.db"
        from signaltranscript.backend import recovery

        real_restore = recovery.restore_sqlite_backup

        def mutate_then_restore(snapshot, output, *, expected_sha256=None):
            with sqlite3.connect(snapshot) as db:
                db.execute("INSERT INTO sample(value) VALUES ('changed')")
            return real_restore(snapshot, output, expected_sha256=expected_sha256)

        with patch(
            "signaltranscript.backend.recovery.restore_sqlite_backup",
            side_effect=mutate_then_restore,
        ):
            with self.assertRaisesRegex(BackupError, "SNAPSHOT_HASH_MISMATCH"):
                stage_verified_recovery(self.snapshot, destination)

        self.assertFalse(destination.exists())

    def test_explicit_expected_hash_is_checked_before_staging(self):
        destination = self.root / "never-mismatch.db"

        with self.assertRaisesRegex(BackupError, "SNAPSHOT_HASH_MISMATCH"):
            stage_verified_recovery(self.snapshot, destination, expected_sha256="0" * 64)

        self.assertFalse(destination.exists())

    def test_invalid_snapshot_never_creates_destination(self):
        invalid = self.root / "invalid.db"
        invalid.write_bytes(b"not sqlite")
        destination = self.root / "never-invalid.db"

        with self.assertRaisesRegex(BackupError, "SQLITE_VERIFICATION_FAILED"):
            stage_verified_recovery(invalid, destination)

        self.assertFalse(destination.exists())

    def test_cli_stages_snapshot_and_prints_receipt_json(self):
        destination = self.root / "cli-staged.db"
        output = io.StringIO()

        with redirect_stdout(output):
            result = main(["--snapshot", str(self.snapshot), "--destination", str(destination)])

        self.assertEqual(result, 0)
        receipt = json.loads(output.getvalue())
        self.assertEqual(receipt["sqlite_user_version"], 2)
        self.assertEqual(len(receipt["source_sha256"]), 64)
        self.assertEqual(len(receipt["restored_sha256"]), 64)
        self.assertTrue(destination.exists())

    def test_cli_hash_mismatch_exits_without_destination(self):
        destination = self.root / "cli-never.db"

        with self.assertRaises(SystemExit):
            main([
                "--snapshot",
                str(self.snapshot),
                "--destination",
                str(destination),
                "--expect-sha256",
                "0" * 64,
            ])

        self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
