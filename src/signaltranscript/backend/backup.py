"""Offline SQLite backup primitives for the local SignalTranscript store.

This module never uploads data and never overwrites an existing database or
backup. It uses SQLite's online backup API instead of copying database/WAL
files independently. Completed snapshots/restores are published atomically
only after their integrity check.
"""

import argparse
from collections.abc import Sequence
from hashlib import sha256
import json
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


def inspect_sqlite_backup(path: Path, *, expected_sha256: str | None = None) -> dict[str, int | str]:
    """Return stable local metadata for one verified snapshot without modifying it."""
    path = Path(path)
    expected = _normalize_expected_sha256(expected_sha256)
    digest_before = _sha256_regular_file(path)
    if expected is not None and digest_before != expected:
        raise BackupError("SNAPSHOT_HASH_MISMATCH")
    try:
        size_bytes = path.stat().st_size
    except OSError as exc:
        raise BackupError("SOURCE_STAT_FAILED") from exc
    db = _open_verified_readonly(path)
    try:
        user_version = int(db.execute("PRAGMA user_version").fetchone()[0])
        page_count = int(db.execute("PRAGMA page_count").fetchone()[0])
        page_size = int(db.execute("PRAGMA page_size").fetchone()[0])
    finally:
        db.close()
    digest_after = _sha256_regular_file(path)
    if digest_after != digest_before:
        raise BackupError("SNAPSHOT_CHANGED_DURING_VERIFICATION")
    return {
        "sha256": digest_after,
        "size_bytes": size_bytes,
        "sqlite_user_version": user_version,
        "sqlite_page_count": page_count,
        "sqlite_page_size": page_size,
    }


def verify_sqlite_backup(path: Path, *, expected_sha256: str | None = None) -> Path:
    """Verify a candidate snapshot without modifying it or its schema."""
    inspect_sqlite_backup(path, expected_sha256=expected_sha256)
    return Path(path)


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
    """Stage a verified backup into a new database path without replacing data."""
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
        verify_sqlite_backup(snapshot, expected_sha256=expected_sha256)
    return restored


def main(argv: Sequence[str] | None = None) -> int:
    """Create, inspect, verify, or safely stage an explicit local backup."""
    parser = argparse.ArgumentParser(
        description="Create, inspect, verify, or stage a local SignalTranscript SQLite snapshot"
    )
    parser.add_argument("--source", type=Path, help="existing SQLite database to snapshot")
    parser.add_argument("--destination", type=Path, help="new path; existing files are never replaced")
    parser.add_argument("--inspect", type=Path, help="verified snapshot to describe as JSON")
    parser.add_argument("--verify", type=Path, help="existing snapshot to verify read-only")
    parser.add_argument("--restore", type=Path, help="verified snapshot to stage into a new database path")
    parser.add_argument("--expect-sha256", help="optional exact snapshot SHA-256 required for inspect/verify/restore")
    args = parser.parse_args(argv)

    modes = sum((args.source is not None, args.inspect is not None, args.verify is not None, args.restore is not None))
    if modes != 1:
        parser.error("choose exactly one of backup creation, inspection, verification, or restore staging")
    if args.source is not None and args.destination is None:
        parser.error("backup creation requires --source and --destination")
    if args.restore is not None and args.destination is None:
        parser.error("restore staging requires --restore and --destination")
    if (args.inspect is not None or args.verify is not None) and args.destination is not None:
        parser.error("inspection/verification does not accept --destination")
    if args.source is not None and args.expect_sha256 is not None:
        parser.error("--expect-sha256 applies only to inspection, verification or restore staging")

    try:
        if args.inspect is not None:
            metadata = inspect_sqlite_backup(args.inspect, expected_sha256=args.expect_sha256)
            print(json.dumps(metadata, sort_keys=True, separators=(",", ":")))
        elif args.verify is not None:
            verify_sqlite_backup(args.verify, expected_sha256=args.expect_sha256)
        elif args.restore is not None:
            restore_sqlite_backup(args.restore, args.destination, expected_sha256=args.expect_sha256)
        else:
            backup_sqlite(args.source, args.destination)
    except (BackupError, OSError):
        parser.error("backup operation could not be completed safely")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
