"""Offline SQLite backup primitive for the local SignalTranscript store.

This module never uploads data and never overwrites an existing backup. It uses
SQLite's online backup API instead of copying database/WAL files independently.
A completed snapshot is published atomically only after its integrity check.
"""

import argparse
from collections.abc import Sequence
from pathlib import Path
import os
import sqlite3
import tempfile


class BackupError(ValueError):
    """The requested local backup cannot be performed safely."""


def backup_sqlite(source: Path, destination: Path) -> Path:
    """Create one consistent SQLite snapshot without replacing existing data."""
    source = Path(source)
    destination = Path(destination)
    if not source.exists() or not source.is_file() or source.is_symlink():
        raise BackupError("SOURCE_NOT_REGULAR_FILE")
    if source.resolve() == destination.resolve():
        raise BackupError("DESTINATION_EQUALS_SOURCE")
    if destination.exists() or destination.is_symlink():
        raise BackupError("DESTINATION_EXISTS")
    if not destination.parent.exists() or not destination.parent.is_dir():
        raise BackupError("DESTINATION_PARENT_MISSING")

    source_db = sqlite3.connect(f"file:{source.resolve()}?mode=ro", uri=True, timeout=5)
    destination_db = None
    temporary: Path | None = None
    try:
        # Refuse arbitrary/non-SQLite input before allocating a snapshot file.
        source_db.execute("PRAGMA schema_version").fetchone()
        source_integrity = source_db.execute("PRAGMA integrity_check").fetchone()
        if source_integrity is None or source_integrity[0] != "ok":
            raise sqlite3.DatabaseError("source integrity check failed")

        # Build beside the destination so publication stays on one filesystem.
        # mkstemp uses O_EXCL and mode 0600; the random file is never a valid
        # advertised backup name while SQLite is still writing it.
        fd, raw_temporary = tempfile.mkstemp(
            prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
        )
        os.close(fd)
        temporary = Path(raw_temporary)
        destination_db = sqlite3.connect(temporary, timeout=5)
        source_db.backup(destination_db)
        integrity = destination_db.execute("PRAGMA integrity_check").fetchone()
        if integrity is None or integrity[0] != "ok":
            raise sqlite3.DatabaseError("backup integrity check failed")
        destination_db.close()
        destination_db = None
        os.chmod(temporary, 0o600)

        # Hard-link publication is atomic and refuses to replace a destination
        # that appeared after the preflight check. Then remove the private temp.
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
        source_db.close()


def main(argv: Sequence[str] | None = None) -> int:
    """Create an explicit local backup; no default destination or overwrite."""
    parser = argparse.ArgumentParser(description="Create a local SignalTranscript SQLite snapshot")
    parser.add_argument("--source", required=True, type=Path,
                        help="existing SQLite database to snapshot")
    parser.add_argument("--destination", required=True, type=Path,
                        help="new backup path; existing files are never replaced")
    args = parser.parse_args(argv)
    try:
        backup_sqlite(args.source, args.destination)
    except (BackupError, OSError):
        # Keep paths and SQLite internals out of terminal/log output.
        parser.error("backup could not be created safely")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
