import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from signaltranscript.backend.backup import BackupError, backup_sqlite
from signaltranscript.backend.recovery import (
    RecoveryReceipt,
    load_recovery_receipt,
    save_recovery_receipt,
    stage_verified_recovery,
    verify_recovery_receipt,
)


class RecoveryReceiptVersionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        active = self.root / "active.db"
        with sqlite3.connect(active) as db:
            db.execute("PRAGMA user_version = 2")
            db.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
            db.execute("INSERT INTO sample(value) VALUES ('checkpoint')")
        self.snapshot = self.root / "snapshot.db"
        backup_sqlite(active, self.snapshot)
        self.destination = self.root / "staged.db"
        self.receipt = stage_verified_recovery(self.snapshot, self.destination)

    def test_new_receipt_declares_current_schema_version(self):
        self.assertEqual(self.receipt.schema_version, 1)
        self.assertEqual(self.receipt.as_dict()["schema_version"], 1)

    def test_parser_rejects_missing_future_and_boolean_schema_versions(self):
        current = self.receipt.as_dict()
        missing = {key: value for key, value in current.items() if key != "schema_version"}
        for payload in (missing, {**current, "schema_version": 2}, {**current, "schema_version": True}):
            with self.subTest(payload=payload):
                with self.assertRaisesRegex(BackupError, "RECOVERY_RECEIPT_INVALID"):
                    RecoveryReceipt.from_dict(payload)

    def test_loader_rejects_unknown_persisted_schema_before_verification(self):
        receipt_path = self.root / "future-receipt.json"
        receipt_path.write_text(json.dumps({**self.receipt.as_dict(), "schema_version": 2}), encoding="utf-8")
        before = self.destination.read_bytes()
        with self.assertRaisesRegex(BackupError, "RECOVERY_RECEIPT_INVALID"):
            load_recovery_receipt(receipt_path)
        self.assertEqual(self.destination.read_bytes(), before)

    def test_save_and_verify_reject_programmatic_unknown_version(self):
        future = RecoveryReceipt(**{**self.receipt.as_dict(), "schema_version": 2})
        receipt_path = self.root / "never.json"
        with self.assertRaisesRegex(BackupError, "RECOVERY_RECEIPT_INVALID"):
            save_recovery_receipt(receipt_path, future)
        self.assertFalse(receipt_path.exists())
        with self.assertRaisesRegex(BackupError, "RECOVERY_RECEIPT_INVALID"):
            verify_recovery_receipt(self.snapshot, self.destination, future)


if __name__ == "__main__":
    unittest.main()
