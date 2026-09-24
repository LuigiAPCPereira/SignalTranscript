"""Offline SQLite backup primitives for the local SignalTranscript store.

This module never uploads data and never overwrites an existing database or
backup. It uses SQLite's online backup API instead of copying database/WAL
files independently. Completed snapshots/restores are published atomically
only after their integrity check.
"""

import argparse
from collections.abc import Sequence
from hashlib import sha256
from pathlib import Path
import os
import re
import sqlite3
import tempfile


class BackupError(ValueError):
    """The requested local backup operation cannot be performed safely."""


def _open_verified_readonly(path: Path) -> sqlite3.Connection:
    """Open a regular SQLite file read-only and require a clean integrity check."""
    path = Path(path)
    if not path.exists() or not path.is_file() or path.is_symlink():
        raise BackupError("SOURCE_NOT_REGULAR_FILE")
    try:
        db = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True, timeout=5)
    except sqlite3.Error as exc:
        raise BackupError("SQLITE_VERIFICATION_FAILED") from exc
    try:
        db.execute("PRAGMA schema_version").fetchone()
        integrity = db.execute("PRAGMA integrity_check").fetchone()
        if integrity is None or integrity[0] != "ok":
            raise sqlite3.DatabaseError("integrity check failed")
    except sqlite3.Error as exc:
        db.close()
        raise BackupError("SQLITE_VERIFICATION_FAILED") from exc
    return db


def _sha256_regular_file(path: Path) -> str:
    """Hash a non-symlink regular file without accepting an unbounded stream."""
    path = Path(path)
    if not path.exists() or not path.is_file() or path.is_symlink():
        raise BackupError("SOURCE_NOT_REGULAR_FILE")
    digest = sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise BackupError("SOURCE_HASH_FAILED") from exc
    return digest.hexdigest()


def _normalize_expected_sha256(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", normalized):
        raise BackupError("EXPECTED_SHA256_INVALID")
    return normalized


def verify_sqlite_backup(path: Path, *, expected_sha256: str | None = None) -> Path:
    """Verify a candidate snapshot without modifying it or its schema.

    When ``expected_sha256`` is supplied, verification also pins the exact
    snapshot bytes selected by the operator. This is useful before restore
    staging when several backups exist; a filename alone is not evidence that
    the intended snapshot was selected.
    """
    path = Path(path)
    expected = _normalize_expected_sha256(expected_sha256)
    before = _sha256_regular_file(path) if expected is not None else None
    if expected is not None and before != expected:
        raise BackupError("SNAPSHOT_HASH_MISMATCH")
    db = _open_verified_readonly(path)
    try:
        db.execute("PRAGMA query_only = ON")
    finally:
        db.close()
    if expected is not None and _sha256_regular_file(path) != expected:
        raise BackupError("SNAPSHOT_CHANGED_DURING_VERIFICATION")
    return path


def _snapshot_to_new_file(source_db: sqlite3.Connection, destination: Path) -> Path:
    """Copy an open SQLite source to a new atomically published private file."""
    destination = Path(destination)
    if destination.exists() or destination.is_symlink():
        raise BackupError("DESTINATION_EXISTS")
    if not destination.parent.exists() or not destination.parent.is_dir():
        raise BackupError("DESTINATION_PARENT_MISSING")

    destination_db = None
    temporary: Path | None = None
    try:
        fd, raw_temporary = tempfile.mkstemp(
            prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
        )
        os.close(fd)
        temporary = Path(raw_temporary)
        destination_db = sqlite3.connect(temporary, timeout=5)
        source_db.backup(destination_db)
        integrity = destination_db.execute("PRAGMA integrity_check").fetchone()
        if integrity is None or integrity[0] != "ok":
            raise sqlite3.DatabaseError("snapshot integrity check failed")
        destination_db.close()
        destination_db = None
        os.chmod(temporary, 0o600)
        try:
            os.link(temporary, destination)
        except FileExistsError as exc:
            raise BackupError("DESTINATION_EXISTS") from exc
        temporary.unlink()
        temporary = None
        return destination
    except BackupError:
        raise
    except sqlite3.Error as exc:
        raise BackupError("SQLITE_BACKUP_FAILED") from exc
    finally:
        if destination_db is not None:
            destination_db.close()
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def backup_sqlite(source: Path, destination: Path) -> Path:
    """Create one consistent SQLite snapshot without replacing existing data."""
    source = Path(source)
    destination = Path(destination)
    if not source.exists() or not source.is_file() or source.is_symlink():
        raise BackupError("SOURCE_NOT_REGULAR_FILE")
    if source.resolve() == destination.resolve():
        raise BackupError("DESTINATION_EQUALS_SOURCE")

    source_db = _open_verified_readonly(source)
    try:
        return _snapshot_to_new_file(source_db, destination)
    finally:
        source_db.close()


def restore_sqlite_backup(
    snapshot: Path, destination: Path, *, expected_sha256: str | None = None
) -> Path:
    """Stage a verified backup into a new database path without replacing data.

    This intentionally does not swap an active database. The caller receives a
    new private SQLite file that can be inspected before any separately
    authorized cutover. An optional SHA-256 pins the exact selected snapshot.
    """
    snapshot = Path(snapshot)
    destination = Path(destination)
    if snapshot.resolve() == destination.resolve():
        raise BackupError("DESTINATION_EQUALS_SOURCE")
    verify_sqlite_backup(snapshot, expected_sha256=expected_sha256)
    source_db = _open_verified_readonly(snapshot)
    try:
        restored = _snapshot_to_new_file(source_db, destination)
    finally:
        source_db.close()
    verify_sqlite_backup(restored)
    if expected_sha256 is not None:
        # Re-check the source after copying. SQLite's backup API gives a
        # consistent destination, while this check refuses to report success if
        # the selected snapshot file itself changed during the restore window.
        verify_sqlite_backup(snapshot, expected_sha256=expected_sha256)
    return restored


def main(argv: Sequence[str] | None = None) -> int:
    """Create, verify, or safely stage an explicit local backup."""
    parser = argparse.ArgumentParser(
        description="Create, verify, or stage a local SignalTranscript SQLite snapshot"
    )
    parser.add_argument("--source", type=Path,
                        help="existing SQLite database to snapshot")
    parser.add_argument("--destination", type=Path,
                        help="new path; existing files are never replaced")
    parser.add_argument("--verify", type=Path,
                        help="existing snapshot to verify read-only")
    parser.add_argument("--restore", type=Path,
                        help="verified snapshot to stage into a new database path")
    parser.add_argument("--expect-sha256",
                        help="optional exact snapshot SHA-256 required for verify/restore")
    args = parser.parse_args(argv)

    modes = sum((args.source is not None, args.verify is not None, args.restore is not None))
    if modes != 1:
        parser.error("choose exactly one of backup creation, verification, or restore staging")
    if args.source is not None and args.destination is None:
        parser.error("backup creation requires --source and --destination")
    if args.restore is not None and args.destination is None:
        parser.error("restore staging requires --restore and --destination")
    if args.verify is not None and args.destination is not None:
        parser.error("verification does not accept --destination")
    if args.source is not None and args.expect_sha256 is not None:
        parser.error("--expect-sha256 applies only to verification or restore staging")

    try:
        if args.verify is not None:
            verify_sqlite_backup(args.verify, expected_sha256=args.expect_sha256)
        elif args.restore is not None:
            restore_sqlite_backup(
                args.restore, args.destination, expected_sha256=args.expect_sha256
            )
        else:
            backup_sqlite(args.source, args.destination)
    except (BackupError, OSError):
        parser.error("backup operation could not be completed safely")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
