"""Offline SQLite backup primitives for the local SignalTranscript store.

This module never uploads data and never overwrites an existing database or
backup. It uses SQLite's online backup API instead of copying database/WAL
files independently. Completed snapshots/restores are published atomically
only after their integrity check.
"""

import argparse
from collections.abc import Sequence
from pathlib import Path
import os
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


def verify_sqlite_backup(path: Path) -> Path:
    """Verify a candidate snapshot without modifying it or its schema."""
    path = Path(path)
    db = _open_verified_readonly(path)
    try:
        db.execute("PRAGMA query_only = ON")
    finally:
        db.close()
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


def restore_sqlite_backup(snapshot: Path, destination: Path) -> Path:
    """Stage a verified backup into a new database path without replacing data.

    This intentionally does not swap an active database. The caller receives a
    new private SQLite file that can be inspected before any separately
    authorized cutover.
    """
    snapshot = Path(snapshot)
    destination = Path(destination)
    if snapshot.resolve() == destination.resolve():
        raise BackupError("DESTINATION_EQUALS_SOURCE")
    source_db = _open_verified_readonly(snapshot)
    try:
        restored = _snapshot_to_new_file(source_db, destination)
    finally:
        source_db.close()
    verify_sqlite_backup(restored)
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

    try:
        if args.verify is not None:
            verify_sqlite_backup(args.verify)
        elif args.restore is not None:
            restore_sqlite_backup(args.restore, args.destination)
        else:
            backup_sqlite(args.source, args.destination)
    except (BackupError, OSError):
        parser.error("backup operation could not be completed safely")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
