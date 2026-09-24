"""Conservative recovery staging for verified local SQLite snapshots.

Recovery is intentionally non-destructive: this module never replaces the active
SignalTranscript database. It pins the source snapshot by SHA-256, delegates
copying to the WAL-safe backup primitive, and returns an auditable receipt for
the newly staged database.
"""

import argparse
from collections.abc import Sequence
from dataclasses import asdict, dataclass
import json
from pathlib import Path

from .backup import BackupError, inspect_sqlite_backup, restore_sqlite_backup


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


def stage_verified_recovery(
    snapshot: Path,
    destination: Path,
    *,
    expected_sha256: str | None = None,
) -> RecoveryReceipt:
    """Stage exactly the snapshot inspected at entry and verify the result.

    When ``expected_sha256`` is supplied it must identify the snapshot before
    any restore work starts. The digest observed during inspection is then
    passed back into ``restore_sqlite_backup``. That primitive verifies the
    snapshot against the digest before and after copying, so a source that
    changes during the recovery window cannot be reported as a successful
    restore. The destination must be a new path; replacement of an active
    database remains an explicit operation outside this module.
    """

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


def main(argv: Sequence[str] | None = None) -> int:
    """Stage a verified snapshot to a new path and emit a machine-readable receipt."""
    parser = argparse.ArgumentParser(
        description="Stage a verified SignalTranscript SQLite snapshot without replacing active data"
    )
    parser.add_argument("--snapshot", required=True, type=Path, help="verified SQLite snapshot to stage")
    parser.add_argument("--destination", required=True, type=Path, help="new database path; never overwritten")
    parser.add_argument("--expect-sha256", help="optional exact SHA-256 required before staging")
    args = parser.parse_args(argv)

    try:
        receipt = stage_verified_recovery(
            args.snapshot,
            args.destination,
            expected_sha256=args.expect_sha256,
        )
    except (BackupError, OSError):
        parser.error("recovery staging could not be completed safely")

    print(json.dumps(receipt.as_dict(), sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
