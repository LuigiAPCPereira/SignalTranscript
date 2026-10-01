"""Offline import of user-supplied SRT/WebVTT cues to the local jobs JSON contract.

No network, downloading, speech recognition or provider access is performed here.
Unsupported timing metadata fails closed rather than inventing a timebase.
"""

import argparse
import json
import os
from pathlib import Path
import re
import stat
import sys

MAX_BYTES = 512_000  # Also the size ceiling of the existing local smoke loader.
MAX_CUES = 4_096     # Existing ImportInput HTTP boundary.
MAX_TEXT = 12_000
STAMP = re.compile(r"(?:(\d{2,}):)?(\d{2}):(\d{2})([.,])(\d{3})\Z")
SETTING = re.compile(r"(?:line|position|size|align|vertical|region):\S+\Z")


class CaptionImportError(ValueError):
    """Safe machine-readable failure; never contain caption contents or paths."""


def _time(value: str, kind: str) -> int:
    parsed = STAMP.fullmatch(value)
    if parsed is None:
        raise CaptionImportError("INVALID_CAPTION_TIMESTAMP")
    hours, minutes, seconds, separator, millis = parsed.groups()
    if separator != ("," if kind == "srt" else ".") or (kind == "srt" and hours is None):
        raise CaptionImportError("INVALID_CAPTION_TIMESTAMP")
    if int(minutes) >= 60 or int(seconds) >= 60:
        raise CaptionImportError("INVALID_CAPTION_TIMESTAMP")
    return ((int(hours or 0) * 60 + int(minutes)) * 60 + int(seconds)) * 1000 + int(millis)


def _cue(block: list[str], kind: str) -> dict[str, object]:
    # Optional SRT numeric label or WebVTT cue identifier; never use it as a
    # canonical ID because source labels need not be unique.
    if "-->" in block[0]:
        header, text = block[0], block[1:]
    elif len(block) >= 3 and "-->" in block[1]:
        if kind == "srt" and not block[0].strip().isdigit():
            raise CaptionImportError("INVALID_CAPTION_CUE")
        header, text = block[1], block[2:]
    else:
        raise CaptionImportError("INVALID_CAPTION_CUE")
    if header.count("-->") != 1:
        raise CaptionImportError("INVALID_CAPTION_TIMESTAMP")
    start_text, right = (part.strip() for part in header.split("-->"))
    tokens = right.split()
    if not tokens:
        raise CaptionImportError("INVALID_CAPTION_TIMESTAMP")
    if len(tokens) > 1 and (kind != "vtt" or any(SETTING.fullmatch(item) is None for item in tokens[1:])):
        raise CaptionImportError("UNSUPPORTED_CAPTION_SETTINGS")
    start, end = _time(start_text, kind), _time(tokens[0], kind)
    if end <= start:
        raise CaptionImportError("INVALID_CAPTION_INTERVAL")
    content = "\n".join(text).strip()
    if not content or len(content) > MAX_TEXT or any(ord(ch) < 32 and ch not in "\n\t" for ch in content) or "\x7f" in content:
        raise CaptionImportError("INVALID_CAPTION_TEXT")
    return {"text": content, "start_ms": start, "end_ms": end}


def parse_captions(raw: str, kind: str) -> list[dict[str, object]]:
    """Parse deliberately bounded, plain SRT or WebVTT; reject malformed cues."""
    if kind not in {"srt", "vtt"}:
        raise CaptionImportError("UNSUPPORTED_CAPTION_FORMAT")
    if not isinstance(raw, str) or len(raw.encode("utf-8")) > MAX_BYTES or "\x00" in raw:
        raise CaptionImportError("INVALID_CAPTION_FILE")
    lines = raw.removeprefix("\ufeff").splitlines()
    if kind == "vtt":
        if not lines or re.fullmatch(r"WEBVTT(?:[ \t]+[^\r\n]*)?", lines[0]) is None:
            raise CaptionImportError("INVALID_WEBVTT_HEADER")
        if len(lines) < 2 or lines[1].strip():
            # X-TIMESTAMP-MAP and other nonzero timebases are not implemented.
            raise CaptionImportError("UNSUPPORTED_WEBVTT_HEADER")
        lines = lines[2:]
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if not line.strip():
            if current:
                blocks.append(current)
                current = []
        else:
            current.append(line)
    if current:
        blocks.append(current)
    segments: list[dict[str, object]] = []
    previous_start = -1
    for block in blocks:
        if kind == "vtt" and (block[0] == "NOTE" or block[0].startswith("NOTE ")
                               or block[0] in {"STYLE", "REGION"}):
            # Explicitly non-spoken WebVTT metadata, not a transcript segment.
            continue
        if len(segments) >= MAX_CUES:
            raise CaptionImportError("TOO_MANY_CAPTION_CUES")
        segment = _cue(block, kind)
        if segment["start_ms"] < previous_start:
            raise CaptionImportError("CAPTION_OUT_OF_ORDER")
        previous_start = segment["start_ms"]
        segment["id"] = f"s{len(segments)+1:06d}"
        segments.append(segment)
    if not segments:
        raise CaptionImportError("EMPTY_CAPTIONS")
    return segments


def convert(path: Path, *, video_id: str, language: str | None = None) -> dict[str, object]:
    """Validate the input before writing anything or invoking another service."""
    if (not isinstance(video_id, str) or not video_id.strip() or len(video_id) > 256
            or (language is not None and (not language.strip() or len(language) > 64))):
        raise CaptionImportError("INVALID_SOURCE_METADATA")
    kind = path.suffix.lower().lstrip(".")
    if kind not in {"srt", "vtt"}:
        raise CaptionImportError("UNSUPPORTED_CAPTION_FORMAT")
    try:
        if not stat.S_ISREG(path.lstat().st_mode) or path.stat().st_size > MAX_BYTES:
            raise CaptionImportError("INVALID_CAPTION_FILE")
        raw = path.read_bytes()
        if len(raw) > MAX_BYTES:
            raise CaptionImportError("INVALID_CAPTION_FILE")
        text = raw.decode("utf-8-sig")
    except (OSError, UnicodeError):
        raise CaptionImportError("INVALID_CAPTION_FILE") from None
    payload = {"video_id": video_id, "source": "manual_import", "language": language,
               "segments": parse_captions(text, kind)}
    if len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) > MAX_BYTES:
        raise CaptionImportError("TRANSCRIPT_TOO_LARGE")
    return payload


def save_private(payload: dict[str, object], output: Path) -> None:
    """Create a private JSON file exclusively, without overwriting old output."""
    try:
        parent = output.parent
        if (not output.is_absolute() or parent.is_symlink() or not parent.is_dir()
                or parent.stat().st_mode & 0o077):
            raise CaptionImportError("OUTPUT_DIRECTORY_NOT_PRIVATE")
        encoded = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        if len(encoded) > MAX_BYTES:
            raise CaptionImportError("TRANSCRIPT_TOO_LARGE")
        descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(descriptor, "wb") as file:
                file.write(encoded)
        except BaseException:
            output.unlink(missing_ok=True)
            raise
    except FileExistsError:
        raise CaptionImportError("OUTPUT_ALREADY_EXISTS") from None
    except OSError:
        raise CaptionImportError("OUTPUT_WRITE_FAILED") from None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Convert permitted local SRT/WebVTT to SignalTranscript JSON without network")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--video-id", required=True)
    parser.add_argument("--language")
    args = parser.parse_args(argv)
    try:
        payload = convert(args.input, video_id=args.video_id, language=args.language)
        save_private(payload, args.output)
        print(f"Importação local: {len(payload['segments'])} segmentos; JSON privado criado. Nenhum envio à IA.")
        return 0
    except CaptionImportError as exc:
        print(f"Caption import: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
