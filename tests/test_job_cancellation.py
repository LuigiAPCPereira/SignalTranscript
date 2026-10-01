"""Offline cancellation contracts: never claim an in-flight remote call was cancelled."""

from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient

from signaltranscript.ai.long_form import compact_source_chars
from signaltranscript.ai.ports import Analysis, Segment, Transcript
from signaltranscript.backend.api import create_app
from signaltranscript.backend.jobs import JobConflict, SQLiteJobs


def transcript() -> Transcript:
    return Transcript(
        "cancel-video", "manual_import",
        (Segment("s1", "One local section", 0, 1000),), language="en",
    )


def budget() -> int:
    return compact_source_chars(transcript()) + 1


class NeverCalledProvider:
    async def analyze(self, part: Transcript) -> Analysis:  # pragma: no cover - safety tripwire
        raise AssertionError("provider must not be called by cancellation tests")


class CancellationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "jobs.db"
        self.jobs = SQLiteJobs(self.path)
        self.jobs.initialize()

    def enqueue(self):
        return self.jobs.enqueue(
            transcript(), provider="fake", model="test-model", revision="v1", max_chars=budget(),
        )

    def test_store_cancels_only_non_running_recoverable_work(self):
        queued = self.enqueue()
        cancelled = self.jobs.cancel(queued.id)
        self.assertEqual(cancelled.state, "CANCELLED")
        self.assertIsNone(cancelled.error_code)
        self.assertIsNone(self.jobs.claim_next())
        with self.assertRaisesRegex(JobConflict, "JOB_NOT_CANCELLABLE"):
            self.jobs.cancel(queued.id)
        with self.assertRaisesRegex(JobConflict, "JOB_NOT_RESUMABLE"):
            self.jobs.resume(
                queued.id, provider="fake", model="test-model", revision="v1", max_chars=budget(),
            )

    def test_running_job_refuses_false_remote_cancellation(self):
        job = self.enqueue()
        claimed = self.jobs.claim_next()
        self.assertEqual(claimed.id, job.id)
        with self.assertRaisesRegex(JobConflict, "REMOTE_CANCELLATION_UNCONFIRMED"):
            self.jobs.cancel(job.id)
        self.assertEqual(self.jobs.get(job.id).state, "RUNNING")

    def test_http_cancel_queued_job_and_reports_conflicts(self):
        job = self.enqueue()
        app = create_app(
            self.path, analysis_provider=NeverCalledProvider(), provider_name="fake",
            model="test-model", revision="v1", max_chars=budget(),
        )
        # Deliberately do not enter TestClient as a context manager: this exercises
        # the HTTP contract without starting the background worker that would race
        # to claim the queued fixture.
        client = TestClient(app)
        response = client.post(f"/api/jobs/{job.id}/cancel")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["state"], "CANCELLED")
        self.assertIsNone(response.json()["result_kind"])
        self.assertEqual(client.post(f"/api/jobs/{job.id}/cancel").status_code, 409)
        self.assertEqual(client.post("/api/jobs/missing/cancel").status_code, 404)


if __name__ == "__main__":
    unittest.main()
