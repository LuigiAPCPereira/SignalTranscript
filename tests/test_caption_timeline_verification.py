"""Offline tests for caption→transcript verification; no network or provider SDK."""

from hashlib import sha256
from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient

from signaltranscript.ai.ports import Analysis, Idea, Transcript
from signaltranscript.backend.api import create_app
from signaltranscript.backend.caption_evidence import (
    CaptionEvidenceError, canonical_transcript_sha256, parse_manifest,
    verify_submitted_caption,
)
from signaltranscript.backend.caption_import import parse_captions
from signaltranscript.backend.jobs import SQLiteJobs

SRT = "1\n00:00:01,000 --> 00:00:02,000\nFala sintética.\n"


def payload() -> dict[str, object]:
    return {
        "video_id": "declared-video",
        "source": "manual_import",
        "language": "pt-BR",
        "segments": parse_captions(SRT, "srt"),
    }


def manifest() -> dict[str, object]:
    data = payload()
    return {
        "schema_version": 2,
        "source_kind": "user_supplied_caption",
        "caption_format": "srt",
        "caption_sha256": sha256(SRT.encode("utf-8")).hexdigest(),
        "transcript_sha256": "b" * 64,
        "transcript_content_sha256": canonical_transcript_sha256(data),
        "declared_video_id": data["video_id"],
        "authorization_status": "UNVERIFIED",
        "video_identity_status": "UNVERIFIED",
        "timeline_match_status": "UNVERIFIED",
        "deep_links_allowed": False,
    }


class FakeProvider:
    async def analyze(self, transcript: Transcript) -> Analysis:
        segment_id = transcript.segments[0].id
        return Analysis(
            "Resumo sintético",
            (Idea("Ideia", "Conteúdo sintético", (segment_id,)),),
            provider="fake", model="test-model",
        )


class CaptionTimelineVerificationTests(unittest.TestCase):
    def test_only_recomputed_caption_timeline_is_promoted(self):
        verified = verify_submitted_caption(
            manifest(), payload(), caption_text=SRT, caption_format="srt",
        )
        self.assertEqual(verified.timeline_match_status, "VERIFIED")
        self.assertEqual(verified.video_identity_status, "UNVERIFIED")
        self.assertEqual(verified.authorization_status, "UNVERIFIED")
        self.assertFalse(verified.deep_links_allowed)

        forged = dict(manifest())
        forged["timeline_match_status"] = "VERIFIED"
        with self.assertRaisesRegex(CaptionEvidenceError, "UNSUPPORTED_VERIFICATION_CLAIM"):
            parse_manifest(forged, payload())
        with self.assertRaisesRegex(CaptionEvidenceError, "EVIDENCE_CAPTION_MISMATCH"):
            verify_submitted_caption(
                manifest(), payload(), caption_text=SRT.replace("sintética", "alterada"),
                caption_format="srt",
            )

    def test_api_persists_verified_caption_match_without_enabling_deep_links(self):
        with tempfile.TemporaryDirectory() as temp:
            db = Path(temp) / "jobs.db"
            app = create_app(
                db, analysis_provider=FakeProvider(), provider_name="fake",
                model="test-model", revision="v1", max_chars=12_000,
            )
            request = dict(payload())
            request["evidence"] = manifest()
            request["caption_verification"] = {"format": "srt", "text": SRT}
            with TestClient(app) as client:
                response = client.post("/api/jobs", json=request)
                self.assertEqual(response.status_code, 202, response.text)
                provenance = response.json()["provenance"]
                self.assertEqual(provenance["timeline_match_status"], "VERIFIED")
                self.assertEqual(provenance["video_identity_status"], "UNVERIFIED")
                self.assertFalse(provenance["deep_links_allowed"])
                job_id = response.json()["id"]
                stored = SQLiteJobs(db).get(job_id)
                self.assertIsNotNone(stored)
                self.assertEqual(stored.evidence.timeline_match_status, "VERIFIED")

            forged_request = dict(payload())
            forged_request["evidence"] = dict(manifest())
            forged_request["evidence"]["timeline_match_status"] = "VERIFIED"
            with TestClient(create_app(
                Path(temp) / "forged.db", analysis_provider=FakeProvider(),
                provider_name="fake", model="test-model", revision="v1", max_chars=12_000,
            )) as client:
                self.assertEqual(client.post("/api/jobs", json=forged_request).status_code, 422)


if __name__ == "__main__":
    unittest.main()
