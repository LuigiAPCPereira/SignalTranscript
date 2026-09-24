from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from signaltranscript.backend.backup import BackupError, backup_sqlite
from signaltranscript.backend.recovery import (
    RecoveryReceipt,
    main,
    save_recovery_receipt,
    stage_verified_recovery,
    verify_recovery_receipt,
)


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

        with patch("signaltranscript.backend.recovery.restore_sqlite_backup", side_effect=mutate_then_restore):
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

    def test_receipt_can_be_verified_read_only(self):
        destination = self.root / "verified.db"
        receipt = stage_verified_recovery(self.snapshot, destination)
        snapshot_before = self.snapshot.read_bytes()
        destination_before = destination.read_bytes()
        verify_recovery_receipt(self.snapshot, destination, receipt)
        self.assertEqual(self.snapshot.read_bytes(), snapshot_before)
        self.assertEqual(destination.read_bytes(), destination_before)

    def test_receipt_detects_staged_database_change(self):
        destination = self.root / "changed.db"
        receipt = stage_verified_recovery(self.snapshot, destination)
        with sqlite3.connect(destination) as db:
            db.execute("INSERT INTO sample(value) VALUES ('later')")
        with self.assertRaisesRegex(BackupError, "SNAPSHOT_HASH_MISMATCH"):
            verify_recovery_receipt(self.snapshot, destination, receipt)

    def test_receipt_rejects_metadata_mismatch(self):
        destination = self.root / "metadata.db"
        receipt = stage_verified_recovery(self.snapshot, destination)
        wrong = RecoveryReceipt(**{**receipt.as_dict(), "sqlite_user_version": 99})
        with self.assertRaisesRegex(BackupError, "RECOVERY_RECEIPT_MISMATCH"):
            verify_recovery_receipt(self.snapshot, destination, wrong)

    def test_receipt_parser_requires_exact_schema_and_integer_types(self):
        destination = self.root / "schema.db"
        receipt = stage_verified_recovery(self.snapshot, destination)
        with self.assertRaisesRegex(BackupError, "RECOVERY_RECEIPT_INVALID"):
            RecoveryReceipt.from_dict({**receipt.as_dict(), "extra": "no"})
        malformed = receipt.as_dict()
        malformed["restored_size_bytes"] = True
        with self.assertRaisesRegex(BackupError, "RECOVERY_RECEIPT_INVALID"):
            RecoveryReceipt.from_dict(malformed)

    def test_receipt_parser_rejects_malformed_hashes_and_impossible_metadata(self):
        destination = self.root / "receipt-invariants.db"
        receipt = stage_verified_recovery(self.snapshot, destination)
        valid = receipt.as_dict()
        invalid_values = (
            ("source_sha256", "g" * 64),
            ("restored_sha256", "0" * 63),
            ("restored_size_bytes", 0),
            ("sqlite_user_version", -1),
            ("sqlite_page_count", 0),
            ("sqlite_page_size", 0),
        )
        for field, value in invalid_values:
            with self.subTest(field=field, value=value):
                with self.assertRaisesRegex(BackupError, "RECOVERY_RECEIPT_INVALID"):
                    RecoveryReceipt.from_dict({**valid, field: value})

    def test_receipt_parser_normalizes_valid_uppercase_hashes(self):
        destination = self.root / "receipt-uppercase.db"
        receipt = stage_verified_recovery(self.snapshot, destination)
        parsed = RecoveryReceipt.from_dict(
            {
                **receipt.as_dict(),
                "source_sha256": receipt.source_sha256.upper(),
                "restored_sha256": receipt.restored_sha256.upper(),
            }
        )
        self.assertEqual(parsed, receipt)

    def test_saved_receipt_is_private_canonical_and_verifiable(self):
        destination = self.root / "receipt-staged.db"
        receipt = stage_verified_recovery(self.snapshot, destination)
        receipt_path = self.root / "recovery.json"
        save_recovery_receipt(receipt_path, receipt)
        self.assertEqual(receipt_path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(
            receipt_path.read_bytes(),
            (json.dumps(receipt.as_dict(), sort_keys=True, separators=(",", ":")) + "\n").encode(),
        )
        verify_recovery_receipt(self.snapshot, destination, RecoveryReceipt.from_dict(json.loads(receipt_path.read_text())))

    def test_saved_receipt_never_overwrites_existing_evidence(self):
        destination = self.root / "receipt-existing-staged.db"
        receipt = stage_verified_recovery(self.snapshot, destination)
        receipt_path = self.root / "existing-receipt.json"
        receipt_path.write_bytes(b"keep")
        with self.assertRaisesRegex(BackupError, "RECOVERY_RECEIPT_EXISTS"):
            save_recovery_receipt(receipt_path, receipt)
        self.assertEqual(receipt_path.read_bytes(), b"keep")

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks unavailable")
    def test_saved_receipt_refuses_existing_symlink(self):
        destination = self.root / "receipt-link-staged.db"
        receipt = stage_verified_recovery(self.snapshot, destination)
        protected = self.root / "protected.txt"
        protected.write_bytes(b"keep")
        link = self.root / "receipt-link.json"
        link.symlink_to(protected)
        with self.assertRaisesRegex(BackupError, "RECOVERY_RECEIPT_EXISTS"):
            save_recovery_receipt(link, receipt)
        self.assertEqual(protected.read_bytes(), b"keep")

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

    def test_cli_can_persist_receipt_without_overwrite(self):
        destination = self.root / "cli-receipt-staged.db"
        receipt_path = self.root / "cli-receipt.json"
        output = io.StringIO()
        with redirect_stdout(output):
            result = main([
                "--snapshot", str(self.snapshot),
                "--destination", str(destination),
                "--receipt-out", str(receipt_path),
            ])
        self.assertEqual(result, 0)
        self.assertEqual(json.loads(output.getvalue()), json.loads(receipt_path.read_text()))
        before = receipt_path.read_bytes()
        second_destination = self.root / "cli-receipt-second.db"
        with self.assertRaises(SystemExit):
            main([
                "--snapshot", str(self.snapshot),
                "--destination", str(second_destination),
                "--receipt-out", str(receipt_path),
            ])
        self.assertEqual(receipt_path.read_bytes(), before)

    def test_cli_hash_mismatch_exits_without_destination(self):
        destination = self.root / "cli-never.db"
        with self.assertRaises(SystemExit):
            main(["--snapshot", str(self.snapshot), "--destination", str(destination), "--expect-sha256", "0" * 64])
        self.assertFalse(destination.exists())

    def test_cli_verifies_saved_receipt_without_mutation(self):
        destination = self.root / "cli-verify.db"
        receipt = stage_verified_recovery(self.snapshot, destination)
        receipt_path = self.root / "receipt.json"
        receipt_path.write_text(json.dumps(receipt.as_dict()), encoding="utf-8")
        before = destination.read_bytes()
        output = io.StringIO()
        with redirect_stdout(output):
            result = main(["--snapshot", str(self.snapshot), "--destination", str(destination), "--verify-receipt", str(receipt_path)])
        self.assertEqual(result, 0)
        self.assertEqual(json.loads(output.getvalue()), receipt.as_dict())
        self.assertEqual(destination.read_bytes(), before)

    def test_cli_rejects_invalid_receipt_without_touching_destination(self):
        destination = self.root / "cli-invalid-receipt.db"
        receipt = stage_verified_recovery(self.snapshot, destination)
        receipt_path = self.root / "bad-receipt.json"
        receipt_path.write_text(json.dumps({**receipt.as_dict(), "extra": 1}), encoding="utf-8")
        before = destination.read_bytes()
        with self.assertRaises(SystemExit):
            main(["--snapshot", str(self.snapshot), "--destination", str(destination), "--verify-receipt", str(receipt_path)])
        self.assertEqual(destination.read_bytes(), before)

    def test_cli_rejects_receipt_out_during_verification(self):
        destination = self.root / "cli-verify-exclusive.db"
        receipt = stage_verified_recovery(self.snapshot, destination)
        receipt_path = self.root / "verify-exclusive.json"
        receipt_path.write_text(json.dumps(receipt.as_dict()), encoding="utf-8")
        with self.assertRaises(SystemExit):
            main([
                "--snapshot", str(self.snapshot),
                "--destination", str(destination),
                "--verify-receipt", str(receipt_path),
                "--receipt-out", str(self.root / "never.json"),
            ])


if __name__ == "__main__":
    unittest.main()
