"""Offline FastAPI/SQLite integration: injected provider, no SDK or network."""

from pathlib import Path
from dataclasses import asdict
import sqlite3
import tempfile
import time
import unittest

from fastapi.testclient import TestClient

from signaltranscript.ai.errors import ProviderFailure
from signaltranscript.ai.long_form import compact_source_chars
from signaltranscript.ai.ports import Analysis, Idea, Segment, Transcript
from signaltranscript.backend.api import create_app
from signaltranscript.backend.caption_evidence import canonical_transcript_sha256, parse_manifest
from signaltranscript.backend.jobs import JobConflict, SQLiteJobs


def transcript() -> Transcript:
    return Transcript("video-1", "manual_import", (
        Segment("s1", "Introduction and first topic", 0, 1000),
        Segment("s2", "Second topic and conclusion", 1000, 2000),
    ), language="en")


def body() -> dict:
    tr = transcript()
    return {"video_id": tr.video_id, "source": tr.source, "language": tr.language,
            "segments": [{"id": s.id, "text": s.text,
                          "start_ms": s.start_ms, "end_ms": s.end_ms} for s in tr.segments]}


def evidence() -> dict[str, object]:
    payload = body()
    return {
        "schema_version": 2,
        "source_kind": "user_supplied_caption",
        "caption_format": "srt",
        "caption_sha256": "a" * 64,
        "transcript_sha256": "b" * 64,
        "transcript_content_sha256": canonical_transcript_sha256(payload),
        "declared_video_id": payload["video_id"],
        "authorization_status": "UNVERIFIED",
        "video_identity_status": "UNVERIFIED",
        "timeline_match_status": "UNVERIFIED",
        "deep_links_allowed": False,
    }


def body_with_evidence() -> dict:
    payload = body()
    payload["evidence"] = evidence()
    return payload


def budget() -> int:
    tr = transcript()
    return compact_source_chars(Transcript(tr.video_id, tr.source, (tr.segments[0],), language=tr.language)) + 1


class FakeSynthesisProvider:
    def __init__(self, *, invalid_reference: bool = False):
        self.calls = 0
        self.invalid_reference = invalid_reference

    async def synthesize(self, transcript: Transcript, sectioned) -> Analysis:
        self.calls += 1
        refs = ("missing",) if self.invalid_reference else tuple(
            segment.id for segment in transcript.segments
        )
        return Analysis(
            "Global summary",
            (Idea("Global topic", "Supported across the transcript", refs),),
            provider="synth-fake", model="synth-model",
        )


class FakeProvider:
    def __init__(self, fail_at: int | None = None):
        self.calls: list[tuple[str, ...]] = []
        self.fail_at = fail_at

    async def analyze(self, part: Transcript) -> Analysis:
        self.calls.append(tuple(seg.id for seg in part.segments))
        if self.fail_at == len(self.calls):
            raise ProviderFailure("TIMEOUT", remote_outcome_unknown=True)
        return Analysis("Section summary", (Idea("Topic", "Speaker says topic", (part.segments[0].id,)),),
                        provider="fake", model="test-model")


def poll(client: TestClient, job_id: str, terminal: set[str] | None = None) -> dict:
    terminal = terminal or {"COMPLETED", "FAILED", "INTERRUPTED", "WAITING_RATE_LIMIT"}
    for _ in range(100):
        result = client.get(f"/api/jobs/{job_id}")
        assert result.status_code == 200
        if result.json()["state"] in terminal:
            return result.json()
        time.sleep(.01)
    raise AssertionError("job did not finish within bounded test window")


class JobStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "jobs.db"
        self.jobs = SQLiteJobs(self.path)
        self.jobs.initialize()

    def test_enqueue_and_claim_are_durable(self):
        job = self.jobs.enqueue(transcript(), provider="fake", model="test-model", revision="v1", max_chars=budget())
        self.assertEqual(job.state, "QUEUED")
        self.assertEqual(job.section_count, 2)
        claimed = SQLiteJobs(self.path).claim_next()
        self.assertEqual(claimed.id, job.id)
        self.assertEqual(claimed.attempts, 1)
        self.assertIsNone(self.jobs.claim_next())
        self.jobs.recover_interrupted()
        self.assertEqual(self.jobs.get(job.id).state, "INTERRUPTED")
        with self.assertRaises(JobConflict):
            self.jobs.resume(job.id, provider="other", model="test-model", revision="v1", max_chars=budget())
        resumed = self.jobs.resume(job.id, provider="fake", model="test-model", revision="v1", max_chars=budget())
        self.assertEqual(resumed.state, "QUEUED")
        self.assertEqual(self.jobs.claim_next().attempts, 2)

    def test_provenance_is_persisted_and_old_database_migrates(self):
        record = parse_manifest(evidence(), body())
        job = self.jobs.enqueue(transcript(), provider="fake", model="test-model", revision="v1",
                                max_chars=budget(), evidence=record)
        reopened = SQLiteJobs(self.path).get(job.id)
        self.assertEqual(reopened.evidence, record)

        legacy = Path(self.tmp.name) / "legacy.db"
        with sqlite3.connect(legacy) as db:
            db.execute("""CREATE TABLE jobs (
                id TEXT PRIMARY KEY, state TEXT NOT NULL, transcript_json TEXT NOT NULL,
                provider TEXT NOT NULL, model TEXT NOT NULL, revision TEXT NOT NULL,
                max_chars INTEGER NOT NULL, section_count INTEGER NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0, error_code TEXT)""")
        migrated = SQLiteJobs(legacy)
        migrated.initialize()
        with sqlite3.connect(legacy) as db:
            columns = {row[1] for row in db.execute("PRAGMA table_info(jobs)")}
        self.assertIn("evidence_json", columns)

    def test_transcript_and_input_limits(self):
        with self.assertRaises(ValueError):
            self.jobs.enqueue(transcript(), provider="", model="test-model", revision="v1", max_chars=budget())
        with self.assertRaises(ValueError):
            self.jobs.enqueue(transcript(), provider="fake", model="test-model", revision="v1", max_chars=1)
        with self.assertRaises(ValueError):
            self.jobs.finish("missing", "RUNNING")

    def test_no_unconditional_resume_or_secret_leak(self):
        job = self.jobs.enqueue(transcript(), provider="fake", model="test-model", revision="v1", max_chars=budget())
        with self.assertRaises(JobConflict):
            self.jobs.resume(job.id, provider="fake", model="test-model", revision="v1", max_chars=budget())
        self.assertIsNone(self.jobs.get("missing"))


class APIIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "jobs.db"

    def app(self, provider, **kwargs):
        synthesis = kwargs.get("synthesis")
        return create_app(
            self.path, analysis_provider=provider, provider_name="fake",
            model=kwargs.get("model", "test-model"), revision="v1", max_chars=budget(),
            synthesis_provider=synthesis,
            synthesis_provider_name="synth-fake" if synthesis is not None else None,
            synthesis_model="synth-model" if synthesis is not None else None,
            synthesis_revision="synth-v1" if synthesis is not None else None,
        )

    def test_full_import_and_section_results_not_global(self):
        fake = FakeProvider()
        with TestClient(self.app(fake)) as client:
            response = client.post("/api/jobs", json=body())
            self.assertEqual(response.status_code, 202)
            self.assertFalse(response.json()["provenance"]["evidence_present"])
            self.assertFalse(response.json()["provenance"]["deep_links_allowed"])
            job_id = response.json()["id"]
            complete = poll(client, job_id)
            self.assertEqual(complete["state"], "COMPLETED")
            self.assertEqual(complete["completed_sections"], 2)
            self.assertEqual(complete["result_kind"], "SECTIONS_ONLY")
            result = client.get(f"/api/jobs/{job_id}/sections")
            self.assertEqual(result.status_code, 200)
            self.assertTrue(result.json()["complete"])
            self.assertEqual(len(result.json()["sections"]), 2)
            self.assertFalse(result.json()["provenance"]["deep_links_allowed"])
            self.assertNotIn("summary", result.json())
            self.assertEqual(client.get("/api/jobs/does-not-exist").status_code, 404)
        self.assertEqual(fake.calls, [("s1",), ("s2",)])

    def test_caption_evidence_is_validated_and_persisted_without_enabling_links(self):
        fake = FakeProvider()
        with TestClient(self.app(fake)) as client:
            response = client.post("/api/jobs", json=body_with_evidence())
            self.assertEqual(response.status_code, 202, response.text)
            provenance = response.json()["provenance"]
            self.assertTrue(provenance["evidence_present"])
            self.assertEqual(provenance["evidence_schema"], 2)
            self.assertEqual(provenance["video_identity_status"], "UNVERIFIED")
            self.assertFalse(provenance["deep_links_allowed"])
            job_id = response.json()["id"]
            stored = SQLiteJobs(self.path).get(job_id)
            self.assertIsNotNone(stored.evidence)
            self.assertEqual(asdict(stored.evidence), evidence())
            self.assertEqual(poll(client, job_id)["state"], "COMPLETED")

        forged = body_with_evidence()
        forged["evidence"]["video_identity_status"] = "VERIFIED"
        changed = body_with_evidence()
        changed["segments"][0]["text"] = "Changed after the manifest"
        wrong_video = body_with_evidence()
        wrong_video["video_id"] = "another-video"
        with TestClient(self.app(FakeProvider())) as client:
            for invalid in (forged, changed, wrong_video):
                with self.subTest(invalid=invalid):
                    self.assertEqual(client.post("/api/jobs", json=invalid).status_code, 422)


    def test_global_synthesis_is_explicit_checkpointed_and_readable_without_new_call(self):
        section_provider = FakeProvider()
        synthesis_provider = FakeSynthesisProvider()
        with TestClient(self.app(section_provider, synthesis=synthesis_provider)) as client:
            created = client.post("/api/jobs", json=body())
            job_id = created.json()["id"]
            self.assertEqual(poll(client, job_id)["result_kind"], "SECTIONS_ONLY")

            with sqlite3.connect(self.path) as db:
                before_table = db.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='global_syntheses'"
                ).fetchone()
            self.assertIsNone(before_table)
            missing = client.get(f"/api/jobs/{job_id}/synthesis")
            self.assertEqual(missing.status_code, 404)
            self.assertEqual(missing.json()["detail"], "SYNTHESIS_NOT_FOUND")
            self.assertEqual(synthesis_provider.calls, 0)
            with sqlite3.connect(self.path) as db:
                after_read_table = db.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='global_syntheses'"
                ).fetchone()
            self.assertIsNone(after_read_table)

            first = client.post(f"/api/jobs/{job_id}/synthesis")
            self.assertEqual(first.status_code, 200, first.text)
            payload = first.json()
            self.assertEqual(payload["result_kind"], "GLOBAL_SYNTHESIS")
            self.assertEqual(payload["analysis"]["summary"], "Global summary")
            self.assertEqual(payload["analysis"]["provider"], "synth-fake")
            self.assertFalse(payload["provenance"]["deep_links_allowed"])

            read_only = client.get(f"/api/jobs/{job_id}/synthesis")
            self.assertEqual(read_only.status_code, 200, read_only.text)
            self.assertEqual(read_only.json(), payload)
            self.assertEqual(synthesis_provider.calls, 1)

            second = client.post(f"/api/jobs/{job_id}/synthesis")
            self.assertEqual(second.status_code, 200, second.text)
            self.assertEqual(second.json(), payload)
            self.assertEqual(synthesis_provider.calls, 1)

            sections = client.get(f"/api/jobs/{job_id}/sections").json()
            self.assertEqual(sections["result_kind"], "SECTIONS_ONLY")
            self.assertNotIn("summary", sections)

    def test_global_synthesis_requires_explicit_configuration_and_complete_sections(self):
        with TestClient(self.app(FakeProvider())) as client:
            job_id = client.post("/api/jobs", json=body()).json()["id"]
            self.assertEqual(poll(client, job_id)["state"], "COMPLETED")
            unavailable = client.post(f"/api/jobs/{job_id}/synthesis")
            self.assertEqual(unavailable.status_code, 409)
            self.assertEqual(unavailable.json()["detail"], "SYNTHESIS_PROVIDER_NOT_CONFIGURED")

        interrupted_sections = FakeProvider(fail_at=1)
        synthesis_provider = FakeSynthesisProvider()
        with TestClient(self.app(interrupted_sections, synthesis=synthesis_provider)) as client:
            job_id = client.post("/api/jobs", json=body()).json()["id"]
            self.assertEqual(poll(client, job_id)["state"], "INTERRUPTED")
            incomplete = client.post(f"/api/jobs/{job_id}/synthesis")
            self.assertEqual(incomplete.status_code, 409)
            self.assertEqual(incomplete.json()["detail"], "SECTIONS_NOT_COMPLETE")
        self.assertEqual(synthesis_provider.calls, 0)

    def test_invalid_global_synthesis_is_not_persisted(self):
        synthesis_provider = FakeSynthesisProvider(invalid_reference=True)
        with TestClient(self.app(FakeProvider(), synthesis=synthesis_provider)) as client:
            job_id = client.post("/api/jobs", json=body()).json()["id"]
            self.assertEqual(poll(client, job_id)["state"], "COMPLETED")
            invalid = client.post(f"/api/jobs/{job_id}/synthesis")
            self.assertEqual(invalid.status_code, 409)
            self.assertEqual(invalid.json()["detail"], "INVALID_SYNTHESIS_CHECKPOINT")
            again = client.post(f"/api/jobs/{job_id}/synthesis")
            self.assertEqual(again.status_code, 409)
        self.assertEqual(synthesis_provider.calls, 2)

    def test_unknown_remote_outcome_waits_for_explicit_resume_and_reuses_prefix(self):
        fake = FakeProvider(fail_at=2)
        with TestClient(self.app(fake)) as client:
            job_id = client.post("/api/jobs", json=body()).json()["id"]
            stopped = poll(client, job_id)
            self.assertEqual(stopped["state"], "INTERRUPTED")
            self.assertEqual(stopped["completed_sections"], 1)
            self.assertEqual(stopped["error_code"], "REMOTE_OUTCOME_UNKNOWN")
        fresh = FakeProvider()
        with TestClient(self.app(fresh)) as client:
            self.assertEqual(client.get(f"/api/jobs/{job_id}").json()["state"], "INTERRUPTED")
            self.assertEqual(client.post(f"/api/jobs/{job_id}/resume").status_code, 202)
            self.assertEqual(poll(client, job_id)["state"], "COMPLETED")
            self.assertEqual(client.post(f"/api/jobs/{job_id}/resume").status_code, 409)
        self.assertEqual(fresh.calls, [("s2",)])

    def test_startup_recovers_running_without_remote_retry(self):
        jobs = SQLiteJobs(self.path)
        jobs.initialize()
        job = jobs.enqueue(transcript(), provider="fake", model="test-model", revision="v1", max_chars=budget())
        jobs.claim_next()
        fake = FakeProvider()
        with TestClient(self.app(fake)) as client:
            self.assertEqual(client.get(f"/api/jobs/{job.id}").json()["state"], "INTERRUPTED")
            self.assertEqual(fake.calls, [])
            client.post(f"/api/jobs/{job.id}/resume")
            self.assertEqual(poll(client, job.id)["state"], "COMPLETED")
        self.assertEqual(len(fake.calls), 2)

    def test_second_process_lock_and_configuration_mismatch(self):
        with TestClient(self.app(FakeProvider())) as first:
            with self.assertRaises(RuntimeError):
                with TestClient(self.app(FakeProvider())):
                    pass
            job_id = first.post("/api/jobs", json=body()).json()["id"]
            self.assertEqual(poll(first, job_id)["state"], "COMPLETED")
        with TestClient(self.app(FakeProvider(), model="changed")) as second:
            self.assertEqual(second.post(f"/api/jobs/{job_id}/resume").status_code, 409)

    def test_bad_segments_rejected_before_queuing(self):
        invalid = body()
        invalid["segments"][0]["end_ms"] = -1
        with TestClient(self.app(FakeProvider())) as client:
            self.assertEqual(client.post("/api/jobs", json=invalid).status_code, 422)
            self.assertEqual(client.post("/api/jobs", json={}).status_code, 422)


if __name__ == "__main__":
    unittest.main()
