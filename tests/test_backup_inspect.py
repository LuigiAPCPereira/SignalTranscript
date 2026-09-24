from contextlib import redirect_stdout
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from signaltranscript.backend.backup import (
    BackupError,
    backup_sqlite,
    inspect_sqlite_backup,
    main,
)


class SQLiteBackupInspectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "jobs.db"
        with sqlite3.connect(self.source) as db:
            db.execute("PRAGMA user_version = 2")
            db.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
            db.execute("INSERT INTO sample(value) VALUES ('checkpoint')")
        self.snapshot = self.root / "snapshot.db"
        backup_sqlite(self.source, self.snapshot)

    def test_inspection_reports_stable_verified_metadata_without_modifying_snapshot(self):
        before = self.snapshot.read_bytes()
        metadata = inspect_sqlite_backup(self.snapshot)
        self.assertEqual(metadata["sha256"], sha256(before).hexdigest())
        self.assertEqual(metadata["size_bytes"], len(before))
        self.assertEqual(metadata["sqlite_user_version"], 2)
        self.assertGreater(metadata["sqlite_page_count"], 0)
        self.assertGreater(metadata["sqlite_page_size"], 0)
        self.assertEqual(self.snapshot.read_bytes(), before)

    def test_inspection_can_pin_exact_snapshot_and_rejects_mismatch(self):
        expected = sha256(self.snapshot.read_bytes()).hexdigest()
        self.assertEqual(
            inspect_sqlite_backup(self.snapshot, expected_sha256=expected.upper())["sha256"],
            expected,
        )
        with self.assertRaisesRegex(BackupError, "SNAPSHOT_HASH_MISMATCH"):
            inspect_sqlite_backup(self.snapshot, expected_sha256="0" * 64)

    def test_cli_inspection_emits_machine_readable_metadata_only(self):
        expected = sha256(self.snapshot.read_bytes()).hexdigest()
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(
                main(["--inspect", str(self.snapshot), "--expect-sha256", expected]),
                0,
            )
        metadata = json.loads(output.getvalue())
        self.assertEqual(metadata["sha256"], expected)
        self.assertEqual(metadata["sqlite_user_version"], 2)
        self.assertNotIn(str(self.snapshot), output.getvalue())

    def test_inspection_rejects_invalid_sqlite(self):
        invalid = self.root / "invalid.db"
        invalid.write_bytes(b"not sqlite")
        with self.assertRaisesRegex(BackupError, "SQLITE_VERIFICATION_FAILED"):
            inspect_sqlite_backup(invalid)


if __name__ == "__main__":
    unittest.main()
