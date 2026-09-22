"""Offline, tamper-evident manifest for a user-supplied caption and its import.

Hashes prove only that a particular pair of local files has not changed since
this manifest was generated. They do NOT prove rights, video identity, sync,
or that a YouTube deep link is valid. Never generate such links from this file.
"""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import stat
import sys

from signaltranscript.backend.caption_import import (
    CaptionImportError, MAX_BYTES, convert, save_private,
)


class CaptionEvidenceError(ValueError):
    """Safe machine code, not filenames or source content."""


def _read_regular(path: Path) -> bytes:
    try:
        details = path.lstat()
        if not stat.S_ISREG(details.st_mode) or details.st_size > MAX_BYTES:
            raise CaptionEvidenceError("INVALID_EVIDENCE_FILE")
        raw = path.read_bytes()
        if len(raw) > MAX_BYTES:
            raise CaptionEvidenceError("INVALID_EVIDENCE_FILE")
        return raw
    except OSError:
        raise CaptionEvidenceError("INVALID_EVIDENCE_FILE") from None


def build_manifest(caption: Path, transcript: Path) -> dict[str, object]:
    """Recompute the importer output to bind exact bytes to the caption source."""
    caption_raw = _read_regular(caption)
    transcript_raw = _read_regular(transcript)
    try:
        parsed = json.loads(transcript_raw.decode("utf-8"))
        if (not isinstance(parsed, dict)
                or set(parsed) != {"video_id", "source", "language", "segments"}
                or parsed["source"] != "manual_import"):
            raise CaptionEvidenceError("INVALID_IMPORTED_TRANSCRIPT")
        expected = convert(caption, video_id=parsed["video_id"], language=parsed["language"])
        if parsed != expected:
            raise CaptionEvidenceError("CAPTION_TRANSCRIPT_MISMATCH")
    except (UnicodeError, ValueError, TypeError, KeyError, CaptionImportError) as exc:
        if isinstance(exc, CaptionEvidenceError):
            raise
        raise CaptionEvidenceError("INVALID_IMPORTED_TRANSCRIPT") from None
    return {
        "schema_version": 1,
        "source_kind": "user_supplied_caption",
        "caption_format": caption.suffix.lower().lstrip("."),
        "caption_sha256": sha256(caption_raw).hexdigest(),
        "transcript_sha256": sha256(transcript_raw).hexdigest(),
        "declared_video_id": parsed["video_id"],
        "authorization_status": "UNVERIFIED",
        "video_identity_status": "UNVERIFIED",
        "timeline_match_status": "UNVERIFIED",
        "deep_links_allowed": False,
    }


def verify_manifest(caption: Path, transcript: Path, manifest: Path) -> None:
    """Reject tampering, unsupported fields, and inflated verification claims."""
    raw = _read_regular(manifest)
    try:
        saved = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError):
        raise CaptionEvidenceError("INVALID_EVIDENCE_MANIFEST") from None
    if not isinstance(saved, dict) or saved != build_manifest(caption, transcript):
        raise CaptionEvidenceError("EVIDENCE_MISMATCH")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline caption evidence (no video verification or HTTP)")
    parser.add_argument("action", choices=("create", "verify"))
    parser.add_argument("--caption", type=Path, required=True)
    parser.add_argument("--transcript", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.action == "create":
            save_private(build_manifest(args.caption, args.transcript), args.manifest)
            print("Manifesto privado criado; correspondência de arquivos verificada, origem do vídeo NÃO verificada.")
        else:
            verify_manifest(args.caption, args.transcript, args.manifest)
            print("Hashes e conversão conferidos; origem do vídeo e sincronização NÃO verificadas.")
        return 0
    except (CaptionEvidenceError, CaptionImportError) as exc:
        print(f"Caption evidence: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
