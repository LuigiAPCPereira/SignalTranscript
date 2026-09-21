"""Offline smoke workflow tests; never import Groq SDK or access external APIs."""

from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from signaltranscript.ai.ports import Analysis, Idea, Transcript
from signaltranscript.backend.serve import AnalysisRegistration, build_app
from signaltranscript.backend.smoke import (
    SmokeFailure, execute, load_fixture, main, verify_sections,
)


class FakeAnalysis:
    def __init__(self):
        self.calls = 0

    async def analyze(self, transcript: Transcript) -> Analysis:
        self.calls += 1
        return Analysis("O autor apresenta um exemplo sintético.", (
            Idea("Exemplo", "O texto foi criado para um teste.",
                 (transcript.segments[0].id,)),
        ), provider="fake", model="example-model")


class SmokeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "transcript.json"
        self.path.write_text('''{"video_id":"synthetic", "source":"manual_import", "language":"pt",
        "segments":[{"id":"s1", "text":"Um exemplo.", "start_ms":0, "end_ms":1000}]}''')
        self.payload, self.transcript = load_fixture(self.path)

    def test_dry_run_does_not_touch_http(self):
        with patch("signaltranscript.backend.smoke.call") as network:
            self.assertEqual(main(["--transcript", str(self.path)]), 0)
            network.assert_not_called()

    def test_submit_requires_explicit_acknowledgment(self):
        with patch("signaltranscript.backend.smoke.call") as network:
            self.assertEqual(main(["--transcript", str(self.path), "--submit",
                                   "--expect-provider", "groq"]), 2)
            network.assert_not_called()

    def test_bad_transcript_rejected_offline(self):
        self.path.write_text('''{"video_id":"synthetic", "source":"manual_import",
          "segments":[{"id":"s1", "text":"A", "start_ms":0,"end_ms":1},
                      {"id":"s1", "text":"B", "start_ms":1,"end_ms":2}]}''')
        with self.assertRaisesRegex(SmokeFailure, "INVALID_TRANSCRIPT"):
            load_fixture(self.path)

    def test_wrong_provider_blocks_submission_before_post(self):
        request = Mock(return_value={"analysis_provider": "fake", "model": "example-model",
                                     "result_kind": "SECTIONS_ONLY"})
        with self.assertRaisesRegex(SmokeFailure, "PROVIDER_CONFIGURATION_MISMATCH"):
            execute(port=8765, provider="groq", payload=self.payload,
                    transcript=self.transcript, max_wait_seconds=1, request=request)
        self.assertEqual(request.call_count, 1)
        self.assertEqual(request.call_args.args[1:3], ("GET", "/api/config"))

    def test_timeout_never_resubmits(self):
        calls = iter([
            {"analysis_provider":"fake", "model":"example-model", "result_kind":"SECTIONS_ONLY"},
            {"id": "job-1"}, {"id": "job-1", "state":"RUNNING"},
        ])
        request = Mock(side_effect=lambda *args: next(calls))
        with patch("signaltranscript.backend.smoke.time.monotonic", return_value=100.0):
            # Execute with no wait: after one poll it must retain job ID.
            with self.assertRaisesRegex(SmokeFailure, "DO_NOT_RESUBMIT"):
                execute(port=8765, provider="fake", payload=self.payload,
                        transcript=self.transcript, max_wait_seconds=0, request=request)
        self.assertEqual(sum(call.args[1] == "POST" for call in request.call_args_list), 1)

    def test_citation_and_missing_coverage_are_rejected(self):
        section = {"index": 0, "segment_ids": ["s1"],
                   "analysis":{"summary":"sum", "ideas":[{"source_segment_ids":["unknown"]}],
                               "provider":"fake", "model":"example-model"}}
        result = {"job_id":"job-1", "complete":True, "result_kind":"SECTIONS_ONLY",
                  "planned_sections":1, "sections":[section]}
        with self.assertRaisesRegex(SmokeFailure, "INVALID_EVIDENCE"):
            verify_sections(result, self.transcript, "job-1", 1, "fake", "example-model")
        section["analysis"]["ideas"] = []
        section["segment_ids"] = ["different"]
        with self.assertRaisesRegex(SmokeFailure, "INCOMPLETE_SEGMENT_COVERAGE"):
            verify_sections(result, self.transcript, "job-1", 1, "fake", "example-model")

    def test_end_to_end_http_with_fake_provider(self):
        fake = FakeAnalysis()
        db_path = Path(self.tmp.name) / "jobs.db"
        app = build_app(provider="fake", db_path=db_path, registry={"fake":
            AnalysisRegistration("fake", "example-model", "example-v1", 12_000, lambda: fake)})
        with TestClient(app) as client:
            def request(base, method, route, body=None):
                response = client.request(method, route, json=body)
                self.assertIn(response.status_code, (200, 202), response.text)
                return response.json()
            job_id, count = execute(port=8765, provider="fake", payload=self.payload,
                                    transcript=self.transcript, max_wait_seconds=10,
                                    request=request, pause=lambda _: time.sleep(.01))
            self.assertEqual(count, 1)
            self.assertTrue(job_id)
            self.assertEqual(fake.calls, 1)


if __name__ == "__main__":
    unittest.main()
