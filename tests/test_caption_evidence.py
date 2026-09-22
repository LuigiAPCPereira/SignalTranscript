"""Only local synthetic captions: never use network, provider, secrets or YouTube."""

from pathlib import Path
import json
import tempfile
import unittest

from signaltranscript.backend.caption_import import convert, save_private
from signaltranscript.backend.caption_evidence import (
    CaptionEvidenceError, build_manifest, main, verify_manifest,
)

SRT = "1\n00:00:01,000 --> 00:00:02,000\nA fala sintética.\n"


class CaptionEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        folder = Path(self.temp.name) / "private"
        folder.mkdir(mode=0o700)
        self.caption = folder / "input.srt"
        self.transcript = folder / "transcript.json"
        self.manifest = folder / "evidence.json"
        self.caption.write_text(SRT, encoding="utf-8")
        save_private(convert(self.caption, video_id="user-declared-id", language="pt-BR"), self.transcript)

    def create(self):
        save_private(build_manifest(self.caption, self.transcript), self.manifest)

    def test_manifest_is_unverified_even_when_timestamp_exists(self):
        self.create()
        evidence = json.loads(self.manifest.read_text())
        self.assertEqual(evidence["authorization_status"], "UNVERIFIED")
        self.assertEqual(evidence["video_identity_status"], "UNVERIFIED")
        self.assertEqual(evidence["timeline_match_status"], "UNVERIFIED")
        self.assertIs(evidence["deep_links_allowed"], False)
        self.assertEqual(evidence["declared_video_id"], "user-declared-id")
        self.assertEqual(len(evidence["caption_sha256"]), 64)
        verify_manifest(self.caption, self.transcript, self.manifest)

    def test_caption_change_invalidates_evidence(self):
        self.create()
        self.caption.write_text(SRT.replace("sintética", "alterada"))
        with self.assertRaises(CaptionEvidenceError):
            verify_manifest(self.caption, self.transcript, self.manifest)

    def test_json_change_invalidates_evidence(self):
        self.create()
        self.transcript.write_text(self.transcript.read_text().replace("sintética", "alterada"))
        with self.assertRaises(CaptionEvidenceError):
            verify_manifest(self.caption, self.transcript, self.manifest)

    def test_rejects_forged_verified_status_and_extra_fields(self):
        self.create()
        record = json.loads(self.manifest.read_text())
        record["video_identity_status"] = "VERIFIED"
        self.manifest.write_text(json.dumps(record))
        with self.assertRaisesRegex(CaptionEvidenceError, "EVIDENCE_MISMATCH"):
            verify_manifest(self.caption, self.transcript, self.manifest)
        record["video_identity_status"] = "UNVERIFIED"
        record["video_url"] = "https://example.invalid/watch"
        self.manifest.write_text(json.dumps(record))
        with self.assertRaisesRegex(CaptionEvidenceError, "EVIDENCE_MISMATCH"):
            verify_manifest(self.caption, self.transcript, self.manifest)

    def test_rejects_transcript_not_generated_from_exact_caption(self):
        data = json.loads(self.transcript.read_text())
        data["segments"][0]["text"] = "Outro texto"
        self.transcript.write_text(json.dumps(data))
        with self.assertRaisesRegex(CaptionEvidenceError, "CAPTION_TRANSCRIPT_MISMATCH"):
            build_manifest(self.caption, self.transcript)

    def test_rejects_symlink_source_or_manifest(self):
        symlink = self.caption.parent / "shortcut.srt"
        symlink.symlink_to(self.caption)
        with self.assertRaisesRegex(CaptionEvidenceError, "INVALID_EVIDENCE_FILE"):
            build_manifest(symlink, self.transcript)
        self.create()
        alias = self.caption.parent / "shortcut.json"
        alias.symlink_to(self.manifest)
        with self.assertRaisesRegex(CaptionEvidenceError, "INVALID_EVIDENCE_FILE"):
            verify_manifest(self.caption, self.transcript, alias)

    def test_cli_create_verify_no_overwrite_and_private_file(self):
        arguments = ["--caption", str(self.caption), "--transcript", str(self.transcript),
                     "--manifest", str(self.manifest)]
        self.assertEqual(main(["create", *arguments]), 0)
        self.assertEqual(self.manifest.stat().st_mode & 0o777, 0o600)
        self.assertEqual(main(["verify", *arguments]), 0)
        self.assertEqual(main(["create", *arguments]), 2)
        self.assertEqual(main(["verify", *arguments]), 0)


if __name__ == "__main__":
    unittest.main()
