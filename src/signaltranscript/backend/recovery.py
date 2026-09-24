"""Conservative recovery staging for verified local SQLite snapshots.

Recovery is intentionally non-destructive: this module never replaces the active
SignalTranscript database.  It pins the source snapshot by SHA-256, delegates
copying to the WAL-safe backup primitive, and returns an auditable receipt for
the newly staged database.
"""

from dataclasses import asdict, dataclass
from pathlib import Path

from .backup import inspect_sqlite_backup, restore_sqlite_backup


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


def stage_verified_recovery(snapshot: Path, destination: Path) -> RecoveryReceipt:
    """Stage exactly the snapshot inspected at entry and verify the result.

    The initial digest is passed back into ``restore_sqlite_backup``.  That
    primitive verifies the snapshot against the digest before and after copying,
    so a source that changes during the recovery window cannot be reported as a
    successful restore.  The destination must be a new path; replacement of an
    active database remains an explicit operation outside this module.
    """

    source = inspect_sqlite_backup(Path(snapshot))
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
