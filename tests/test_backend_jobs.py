"""Offline FastAPI/SQLite integration: injected provider, no SDK or network."""

from pathlib import Path
import tempfile
import time
import unittest

from fastapi.testclient import TestClient

from signaltranscript.ai.errors import ProviderFailure
from signaltranscript.ai.long_form import compact_source_chars
from signaltranscript.ai.ports import Analysis, Idea, Segment, Transcript
from signaltranscript.backend.api import create_app
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


def budget() -> int:
    tr = transcript()
    return compact_source_chars(Transcript(tr.video_id, tr.source, (tr.segments[0],), language=tr.language)) + 1


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
        return create_app(self.path, analysis_provider=provider, provider_name="fake",
                          model=kwargs.get("model", "test-model"), revision="v1", max_chars=budget())

    def test_full_import_and_section_results_not_global(self):
        fake = FakeProvider()
        with TestClient(self.app(fake)) as client:
            response = client.post("/api/jobs", json=body())
            self.assertEqual(response.status_code, 202)
            job_id = response.json()["id"]
            complete = poll(client, job_id)
            self.assertEqual(complete["state"], "COMPLETED")
            self.assertEqual(complete["completed_sections"], 2)
            self.assertEqual(complete["result_kind"], "SECTIONS_ONLY")
            result = client.get(f"/api/jobs/{job_id}/sections")
            self.assertEqual(result.status_code, 200)
            self.assertTrue(result.json()["complete"])
            self.assertEqual(len(result.json()["sections"]), 2)
            self.assertNotIn("summary", result.json())
            self.assertEqual(client.get("/api/jobs/does-not-exist").status_code, 404)
        self.assertEqual(fake.calls, [("s1",), ("s2",)])

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
