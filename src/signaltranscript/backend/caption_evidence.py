"""Offline, tamper-evident evidence for a user-supplied caption import.

Hashes bind local files and canonical transcript content. They do NOT prove
rights, video identity, synchronization with a real video, or by themselves
that a temporal deep link is valid.
"""

import argparse
from collections.abc import Mapping
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
import json
from pathlib import Path
import re
import stat
import sys

from signaltranscript.backend.caption_import import (
    CaptionImportError, MAX_BYTES, convert, parse_captions, save_private,
)

MANIFEST_FIELDS = frozenset({
    "schema_version", "source_kind", "caption_format", "caption_sha256",
    "transcript_sha256", "transcript_content_sha256", "declared_video_id",
    "authorization_status", "video_identity_status", "timeline_match_status",
    "deep_links_allowed",
})
TRANSCRIPT_FIELDS = frozenset({"video_id", "source", "language", "segments"})
HEX_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class CaptionEvidenceError(ValueError):
    """Safe machine code, not filenames or source content."""


@dataclass(frozen=True, slots=True)
class CaptionEvidence:
    schema_version: int
    source_kind: str
    caption_format: str
    caption_sha256: str
    transcript_sha256: str
    transcript_content_sha256: str
    declared_video_id: str
    authorization_status: str
    video_identity_status: str
    timeline_match_status: str
    deep_links_allowed: bool


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


def canonical_transcript_sha256(payload: Mapping[str, object]) -> str:
    """Hash the API import contract independent of JSON whitespace/key order."""
    if not isinstance(payload, Mapping) or set(payload) != TRANSCRIPT_FIELDS:
        raise CaptionEvidenceError("INVALID_IMPORTED_TRANSCRIPT")
    try:
        encoded = json.dumps(
            dict(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError):
        raise CaptionEvidenceError("INVALID_IMPORTED_TRANSCRIPT") from None
    return sha256(encoded).hexdigest()


def parse_manifest(
    data: object, transcript_payload: Mapping[str, object], *,
    allow_verified_timeline: bool = False,
) -> CaptionEvidence:
    """Validate a manifest against the exact canonical transcript.

    User input may never claim verification. ``allow_verified_timeline`` is for
    reloading a record that this process already promoted after re-parsing the
    submitted caption bytes with :func:`verify_submitted_caption`.
    """
    if not isinstance(data, Mapping) or set(data) != MANIFEST_FIELDS:
        raise CaptionEvidenceError("INVALID_EVIDENCE_MANIFEST")
    if type(data["schema_version"]) is not int or data["schema_version"] != 2:
        raise CaptionEvidenceError("UNSUPPORTED_EVIDENCE_SCHEMA")
    if data["source_kind"] != "user_supplied_caption" or data["caption_format"] not in {"srt", "vtt"}:
        raise CaptionEvidenceError("INVALID_EVIDENCE_MANIFEST")
    for key in ("caption_sha256", "transcript_sha256", "transcript_content_sha256"):
        if not isinstance(data[key], str) or HEX_SHA256.fullmatch(data[key]) is None:
            raise CaptionEvidenceError("INVALID_EVIDENCE_MANIFEST")
    if (not isinstance(data["declared_video_id"], str) or not data["declared_video_id"].strip()
            or len(data["declared_video_id"]) > 256):
        raise CaptionEvidenceError("INVALID_EVIDENCE_MANIFEST")
    if data["authorization_status"] != "UNVERIFIED" or data["video_identity_status"] != "UNVERIFIED":
        raise CaptionEvidenceError("UNSUPPORTED_VERIFICATION_CLAIM")
    allowed_timeline = {"UNVERIFIED", "VERIFIED"} if allow_verified_timeline else {"UNVERIFIED"}
    if data["timeline_match_status"] not in allowed_timeline:
        raise CaptionEvidenceError("UNSUPPORTED_VERIFICATION_CLAIM")
    if data["deep_links_allowed"] is not False:
        raise CaptionEvidenceError("UNSUPPORTED_VERIFICATION_CLAIM")
    if transcript_payload.get("source") != "manual_import":
        raise CaptionEvidenceError("EVIDENCE_SOURCE_MISMATCH")
    if data["declared_video_id"] != transcript_payload.get("video_id"):
        raise CaptionEvidenceError("EVIDENCE_VIDEO_ID_MISMATCH")
    if data["transcript_content_sha256"] != canonical_transcript_sha256(transcript_payload):
        raise CaptionEvidenceError("EVIDENCE_TRANSCRIPT_MISMATCH")
    return CaptionEvidence(**{key: data[key] for key in MANIFEST_FIELDS})  # type: ignore[arg-type]


def verify_submitted_caption(
    data: object, transcript_payload: Mapping[str, object], *, caption_text: str,
    caption_format: str,
) -> CaptionEvidence:
    """Promote only caption→transcript timeline correspondence after recomputation.

    This verifies that the exact submitted SRT/VTT bytes hash to the manifest and
    parse to the exact transcript segments/timestamps. It does NOT establish that
    the caption belongs to the declared video or is synchronized to that video,
    so identity/authorization stay UNVERIFIED and deep links stay disabled.
    """
    evidence = parse_manifest(data, transcript_payload)
    if caption_format != evidence.caption_format or caption_format not in {"srt", "vtt"}:
        raise CaptionEvidenceError("EVIDENCE_CAPTION_FORMAT_MISMATCH")
    if not isinstance(caption_text, str):
        raise CaptionEvidenceError("INVALID_CAPTION_FILE")
    try:
        raw = caption_text.encode("utf-8")
    except UnicodeError:
        raise CaptionEvidenceError("INVALID_CAPTION_FILE") from None
    if len(raw) > MAX_BYTES or sha256(raw).hexdigest() != evidence.caption_sha256:
        raise CaptionEvidenceError("EVIDENCE_CAPTION_MISMATCH")
    try:
        expected = {
            "video_id": transcript_payload.get("video_id"),
            "source": "manual_import",
            "language": transcript_payload.get("language"),
            "segments": parse_captions(caption_text, caption_format),
        }
    except CaptionImportError as exc:
        raise CaptionEvidenceError(str(exc)) from None
    if expected != dict(transcript_payload):
        raise CaptionEvidenceError("CAPTION_TRANSCRIPT_MISMATCH")
    return replace(evidence, timeline_match_status="VERIFIED")


def build_manifest(caption: Path, transcript: Path) -> dict[str, object]:
    """Recompute importer output and bind exact files plus canonical API content."""
    caption_raw = _read_regular(caption)
    transcript_raw = _read_regular(transcript)
    try:
        parsed = json.loads(transcript_raw.decode("utf-8"))
        if (not isinstance(parsed, dict) or set(parsed) != TRANSCRIPT_FIELDS
                or parsed["source"] != "manual_import"):
            raise CaptionEvidenceError("INVALID_IMPORTED_TRANSCRIPT")
        expected = convert(caption, video_id=parsed["video_id"], language=parsed["language"])
        if parsed != expected:
            raise CaptionEvidenceError("CAPTION_TRANSCRIPT_MISMATCH")
    except (UnicodeError, ValueError, TypeError, KeyError, CaptionImportError) as exc:
        if isinstance(exc, CaptionEvidenceError):
            raise
        raise CaptionEvidenceError("INVALID_IMPORTED_TRANSCRIPT") from None
    record = {
        "schema_version": 2,
        "source_kind": "user_supplied_caption",
        "caption_format": caption.suffix.lower().lstrip("."),
        "caption_sha256": sha256(caption_raw).hexdigest(),
        "transcript_sha256": sha256(transcript_raw).hexdigest(),
        "transcript_content_sha256": canonical_transcript_sha256(parsed),
        "declared_video_id": parsed["video_id"],
        "authorization_status": "UNVERIFIED",
        "video_identity_status": "UNVERIFIED",
        "timeline_match_status": "UNVERIFIED",
        "deep_links_allowed": False,
    }
    return asdict(parse_manifest(record, parsed))


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
