"""No HTTP, SDK, credentials, ffmpeg, YouTube or network in these tests."""

from pathlib import Path
import json
import os
import tempfile
import unittest

from signaltranscript.backend.caption_import import (
    CaptionImportError, convert, main, parse_captions, save_private,
)
from signaltranscript.backend.api import ImportInput
from signaltranscript.ai.ports import Segment, Transcript

SRT = """1
00:00:01,500 --> 00:00:03,000
Primeiro bloco.

2
00:00:03,000 --> 00:00:04,250
Segundo bloco.
Linha adicional.
"""
VTT = """WEBVTT

NOTE original caption source
Do not narrate this note.

segment a
00:01.200 --> 00:02.000 align:start
<c>Introdução.</c>

00:02.000 --> 00:03.500
Conclusão.
"""


class CaptionImportTests(unittest.TestCase):
    def test_srt_order_text_and_millisecond_precision(self):
        segments = parse_captions(SRT, "srt")
        self.assertEqual([segment["id"] for segment in segments], ["s000001", "s000002"])
        self.assertEqual([(x["start_ms"], x["end_ms"]) for x in segments],
                         [(1500, 3000), (3000, 4250)])
        self.assertEqual(segments[1]["text"], "Segundo bloco.\nLinha adicional.")

    def test_vtt_header_settings_note_and_tag_are_preserved(self):
        segments = parse_captions("\ufeff" + VTT, "vtt")
        self.assertEqual([(x["start_ms"], x["end_ms"]) for x in segments], [(1200, 2000), (2000, 3500)])
        self.assertEqual(segments[0]["text"], "<c>Introdução.</c>")
        self.assertEqual(len(segments), 2)

    def test_same_start_and_overlapping_cues_are_preserved(self):
        self.assertEqual(len(parse_captions("00:00:01,000 --> 00:00:02,000\na\n\n"
                                           "00:00:01,000 --> 00:00:03,000\nb", "srt")), 2)

    def test_out_of_order_rejected_without_reordering(self):
        with self.assertRaisesRegex(CaptionImportError, "CAPTION_OUT_OF_ORDER"):
            parse_captions("00:00:02,000 --> 00:00:03,000\na\n\n"
                           "00:00:01,000 --> 00:00:04,000\nb", "srt")

    def test_invalid_intervals_and_minutes_rejected(self):
        for input_text in ("00:00:02,000 --> 00:00:02,000\na",
                           "00:60:00,000 --> 00:61:01,000\na",
                           "00:00:01,000 --> 00:00:01,001 unexpected\na"):
            with self.subTest(input_text=input_text), self.assertRaises(CaptionImportError):
                parse_captions(input_text, "srt")

    def test_missing_header_and_timebase_rejected(self):
        for content in ("00:01.000 --> 00:02.000\na",
                        "WEBVTT\nX-TIMESTAMP-MAP=LOCAL:00:00:00.000,MPEGTS:0\n\n00:01.000 --> 00:02.000\na"):
            with self.subTest(content=content), self.assertRaises(CaptionImportError):
                parse_captions(content, "vtt")

    def test_bad_cue_and_invalid_control_character_rejected(self):
        for content in ("1\n00:00:01,000 --> 00:00:02,000\n",
                        "1\n00:00:01,000 --> 00:00:02,000\nabc\x01def",
                        "not a caption"):
            with self.subTest(content=content), self.assertRaises(CaptionImportError):
                parse_captions(content, "srt")

    def test_all_metadata_is_not_speech(self):
        with self.assertRaisesRegex(CaptionImportError, "EMPTY_CAPTIONS"):
            parse_captions("WEBVTT\n\nNOTE\nNote only.", "vtt")

    def test_more_than_http_max_cues_rejected(self):
        cue = "00:00:01,000 --> 00:00:02,000\na\n\n"
        with self.assertRaisesRegex(CaptionImportError, "TOO_MANY_CAPTION_CUES"):
            parse_captions(cue * 4097, "srt")

    def test_convert_matches_real_import_boundary_and_domain(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "example.srt"
            source.write_text(SRT, encoding="utf-8")
            data = convert(source, video_id="permitted-video", language="pt-BR")
            schema = ImportInput.model_validate(data)
            self.assertEqual(schema.source, "manual_import")
            transcript = Transcript(schema.video_id, schema.source,
                                    tuple(Segment(**x.model_dump()) for x in schema.segments),
                                    language=schema.language)
            self.assertEqual(len(transcript.segments), 2)

    def test_symlink_and_invalid_format_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "caption.srt"
            source.write_text(SRT)
            link = Path(tmp) / "link.srt"
            link.symlink_to(source)
            with self.assertRaisesRegex(CaptionImportError, "INVALID_CAPTION_FILE"):
                convert(link, video_id="v")
            with self.assertRaisesRegex(CaptionImportError, "UNSUPPORTED_CAPTION_FORMAT"):
                convert(Path(tmp) / "file.txt", video_id="v")

    def test_private_output_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / "private"
            directory.mkdir(mode=0o700)
            dest = directory / "input.json"
            payload = {"video_id": "v", "source": "manual_import", "segments": []}
            save_private(payload, dest)
            self.assertEqual(dest.stat().st_mode & 0o777, 0o600)
            self.assertEqual(json.loads(dest.read_text()), payload)
            with self.assertRaisesRegex(CaptionImportError, "OUTPUT_ALREADY_EXISTS"):
                save_private(payload, dest)
            self.assertEqual(json.loads(dest.read_text()), payload)
            directory.chmod(0o755)
            with self.assertRaisesRegex(CaptionImportError, "OUTPUT_DIRECTORY_NOT_PRIVATE"):
                save_private(payload, directory / "other.json")

    def test_cli_is_offline_and_creates_loadable_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / "private"
            directory.mkdir(mode=0o700)
            source, output = Path(tmp) / "input.srt", directory / "transcript.json"
            source.write_text(SRT)
            self.assertEqual(main(["--input", str(source), "--output", str(output),
                                   "--video-id", "v", "--language", "pt"]), 0)
            self.assertEqual(len(ImportInput.model_validate(json.loads(output.read_text())).segments), 2)
            self.assertEqual(main(["--input", str(source), "--output", str(output),
                                   "--video-id", "v"]), 2)


if __name__ == "__main__":
    unittest.main()
