"""Conservative recovery staging for verified local SQLite snapshots.

Recovery is intentionally non-destructive: this module never replaces the active
SignalTranscript database. It pins the source snapshot by SHA-256, delegates
copying to the WAL-safe backup primitive, and returns an auditable receipt for
the newly staged database.
"""

import argparse
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import string

from .backup import BackupError, inspect_sqlite_backup, restore_sqlite_backup


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in string.hexdigits for character in value)
    )


@dataclass(frozen=True, slots=True)
class RecoveryReceipt:
    """Verified identities for one non-destructive restore-staging operation."""

    source_sha256: str
    restored_sha256: str
    restored_size_bytes: int
    sqlite_user_version: int
    sqlite_page_count: int
    sqlite_page_size: int

    def as_dict(self) -> dict[str, int | str]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "RecoveryReceipt":
        """Parse only a physically plausible exact receipt schema.

        Receipts can be stored and supplied later, so parsing is deliberately
        fail-closed: no extra fields, type coercion, malformed digests, negative
        counters, or impossible zero-sized SQLite metadata are accepted.
        """
        expected = {
            "source_sha256",
            "restored_sha256",
            "restored_size_bytes",
            "sqlite_user_version",
            "sqlite_page_count",
            "sqlite_page_size",
        }
        if set(value) != expected:
            raise BackupError("RECOVERY_RECEIPT_INVALID")
        try:
            source_sha256 = value["source_sha256"]
            restored_sha256 = value["restored_sha256"]
            restored_size_bytes = value["restored_size_bytes"]
            sqlite_user_version = value["sqlite_user_version"]
            sqlite_page_count = value["sqlite_page_count"]
            sqlite_page_size = value["sqlite_page_size"]
            integers = (
                restored_size_bytes,
                sqlite_user_version,
                sqlite_page_count,
                sqlite_page_size,
            )
            if not _is_sha256(source_sha256) or not _is_sha256(restored_sha256):
                raise TypeError
            if any(type(item) is not int for item in integers):
                raise TypeError
            if restored_size_bytes <= 0 or sqlite_user_version < 0:
                raise ValueError
            if sqlite_page_count <= 0 or sqlite_page_size <= 0:
                raise ValueError
            return cls(
                source_sha256=source_sha256.lower(),
                restored_sha256=restored_sha256.lower(),
                restored_size_bytes=restored_size_bytes,
                sqlite_user_version=sqlite_user_version,
                sqlite_page_count=sqlite_page_count,
                sqlite_page_size=sqlite_page_size,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise BackupError("RECOVERY_RECEIPT_INVALID") from exc


def stage_verified_recovery(
    snapshot: Path,
    destination: Path,
    *,
    expected_sha256: str | None = None,
) -> RecoveryReceipt:
    """Stage exactly the snapshot inspected at entry and verify the result."""
    source = inspect_sqlite_backup(Path(snapshot), expected_sha256=expected_sha256)
    source_sha256 = str(source["sha256"])

    restored = restore_sqlite_backup(
        Path(snapshot),
        Path(destination),
        expected_sha256=source_sha256,
    )
    result = inspect_sqlite_backup(restored)

    return RecoveryReceipt(
        source_sha256=source_sha256,
        restored_sha256=str(result["sha256"]),
        restored_size_bytes=int(result["size_bytes"]),
        sqlite_user_version=int(result["sqlite_user_version"]),
        sqlite_page_count=int(result["sqlite_page_count"]),
        sqlite_page_size=int(result["sqlite_page_size"]),
    )


def verify_recovery_receipt(
    snapshot: Path,
    destination: Path,
    receipt: RecoveryReceipt,
) -> None:
    """Verify that a receipt still describes the exact source and staged DB.

    This is read-only. It intentionally does not repair, replace, migrate, or
    promote either database. A mismatch is a failed verification, never a
    partial success.
    """
    source = inspect_sqlite_backup(Path(snapshot), expected_sha256=receipt.source_sha256)
    restored = inspect_sqlite_backup(Path(destination), expected_sha256=receipt.restored_sha256)
    observed = RecoveryReceipt(
        source_sha256=str(source["sha256"]),
        restored_sha256=str(restored["sha256"]),
        restored_size_bytes=int(restored["size_bytes"]),
        sqlite_user_version=int(restored["sqlite_user_version"]),
        sqlite_page_count=int(restored["sqlite_page_count"]),
        sqlite_page_size=int(restored["sqlite_page_size"]),
    )
    if observed != receipt:
        raise BackupError("RECOVERY_RECEIPT_MISMATCH")


def _receipt_bytes(receipt: RecoveryReceipt) -> bytes:
    return (json.dumps(receipt.as_dict(), sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def save_recovery_receipt(path: Path, receipt: RecoveryReceipt) -> Path:
    """Persist a private receipt without following links or overwriting evidence."""
    target = Path(path)
    if not target.parent.is_dir():
        raise BackupError("RECOVERY_RECEIPT_DESTINATION_INVALID")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(target, flags, 0o600)
    except FileExistsError as exc:
        raise BackupError("RECOVERY_RECEIPT_EXISTS") from exc
    except OSError as exc:
        raise BackupError("RECOVERY_RECEIPT_WRITE_FAILED") from exc
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(_receipt_bytes(receipt))
            handle.flush()
            os.fsync(handle.fileno())
    except OSError as exc:
        try:
            target.unlink()
        except OSError:
            pass
        raise BackupError("RECOVERY_RECEIPT_WRITE_FAILED") from exc
    return target


def _load_receipt(path: Path) -> RecoveryReceipt:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BackupError("RECOVERY_RECEIPT_INVALID") from exc
    if not isinstance(raw, dict):
        raise BackupError("RECOVERY_RECEIPT_INVALID")
    return RecoveryReceipt.from_dict(raw)


def main(argv: Sequence[str] | None = None) -> int:
    """Stage a snapshot or verify an earlier recovery receipt, without cutover."""
    parser = argparse.ArgumentParser(
        description="Stage or verify SignalTranscript SQLite recovery without replacing active data"
    )
    parser.add_argument("--snapshot", required=True, type=Path, help="verified SQLite source snapshot")
    parser.add_argument("--destination", required=True, type=Path, help="staged database path")
    parser.add_argument("--expect-sha256", help="optional exact SHA-256 required before staging")
    parser.add_argument("--verify-receipt", type=Path, help="read-only verification of a prior receipt JSON")
    parser.add_argument("--receipt-out", type=Path, help="persist a new private receipt without overwrite")
    args = parser.parse_args(argv)

    if args.verify_receipt is not None and args.expect_sha256 is not None:
        parser.error("--expect-sha256 is only valid while staging")
    if args.verify_receipt is not None and args.receipt_out is not None:
        parser.error("--receipt-out is only valid while staging")

    try:
        if args.verify_receipt is not None:
            receipt = _load_receipt(args.verify_receipt)
            verify_recovery_receipt(args.snapshot, args.destination, receipt)
        else:
            receipt = stage_verified_recovery(
                args.snapshot,
                args.destination,
                expected_sha256=args.expect_sha256,
            )
            if args.receipt_out is not None:
                save_recovery_receipt(args.receipt_out, receipt)
    except (BackupError, OSError):
        parser.error("recovery operation could not be completed safely")

    print(json.dumps(receipt.as_dict(), sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
