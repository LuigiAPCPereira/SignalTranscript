"""Offline composition/CLI checks: no Groq SDK, credentials or network calls."""

from hashlib import sha256
import json
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from signaltranscript.ai.adapters.groq_analysis import (
    ANALYSIS_SCHEMA, MAX_COMPLETION_TOKENS, MAX_INPUT_CHARS, MODEL, SYSTEM_INSTRUCTIONS,
)
from signaltranscript.ai.ports import Analysis, Idea, Transcript
from signaltranscript.backend.jobs import SQLiteJobs
from signaltranscript.ai.ports import Segment
from signaltranscript.backend.serve import (
    AnalysisRegistration, available_providers, build_app, groq_revision, main,
)


class FakeAnalysis:
    def __init__(self):
        self.calls = 0
        self.closed = False

    async def analyze(self, transcript: Transcript) -> Analysis:
        self.calls += 1
        return Analysis("Local test summary", (
            Idea("Idea", "Statement by speaker", (transcript.segments[0].id,)),
        ), provider="fake", model="test-model")

    async def aclose(self) -> None:
        self.closed = True


def registration(fake: FakeAnalysis) -> AnalysisRegistration:
    return AnalysisRegistration("fake", "test-model", "test-revision", 12_000, lambda: fake)


class LocalServeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "jobs.db"

    def test_groq_is_registered_without_constructing_sdk_client(self):
        registered = available_providers()
        self.assertEqual(set(registered), {"groq"})
        self.assertEqual(registered["groq"].name, "groq")
        self.assertEqual(registered["groq"].model, MODEL)
        self.assertEqual(registered["groq"].max_chars, MAX_INPUT_CHARS)
        self.assertEqual(registered["groq"].revision, groq_revision())

    def test_revision_fingerprints_actual_groq_analysis_contract(self):
        material = {
            "model": MODEL, "system_instructions": SYSTEM_INSTRUCTIONS,
            "analysis_schema": ANALYSIS_SCHEMA,
            "max_completion_tokens": MAX_COMPLETION_TOKENS,
            "response_mode": "json_schema_strict_v1",
        }
        canonical = json.dumps(material, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        self.assertEqual(groq_revision(), "groq-analysis-" + sha256(canonical.encode()).hexdigest())

    def test_unknown_provider_does_not_construct_another_provider(self):
        fake = FakeAnalysis()
        with self.assertRaisesRegex(ValueError, "ANALYSIS_PROVIDER_NOT_REGISTERED"):
            build_app(provider="missing", db_path=self.db, registry={"fake": registration(fake)})
        self.assertEqual(fake.calls, 0)

    def test_missing_key_fails_before_sdk_import_or_server_start(self):
        with patch.dict(os.environ, {"GROQ_API_KEY": ""}):
            with self.assertRaisesRegex(RuntimeError, "GROQ_API_KEY"):
                build_app(provider="groq", db_path=self.db)
        self.assertFalse(self.db.exists())

    def test_invalid_registration_rejected_before_factory(self):
        fake = FakeAnalysis()
        invalid = AnalysisRegistration("other", "test-model", "v1", 12_000, lambda: fake)
        with self.assertRaisesRegex(ValueError, "INVALID_ANALYSIS_REGISTRATION"):
            build_app(provider="fake", db_path=self.db, registry={"fake": invalid})
        self.assertFalse(fake.closed)

    def test_full_http_job_uses_selected_provider_and_closes_on_shutdown(self):
        fake = FakeAnalysis()
        app = build_app(provider="fake", db_path=self.db, registry={"fake": registration(fake)})
        payload = {"video_id": "v1", "source": "manual_import", "language": "pt",
                   "segments": [{"id": "seg-1", "text": "Uma informação do autor.",
                                 "start_ms": 0, "end_ms": 1000}]}
        with TestClient(app) as client:
            created = client.post("/api/jobs", json=payload)
            self.assertEqual(created.status_code, 202)
            job_id = created.json()["id"]
            for _ in range(100):
                current = client.get(f"/api/jobs/{job_id}").json()
                if current["state"] == "COMPLETED":
                    break
                time.sleep(.01)
            else:
                self.fail("job never completed")
            self.assertEqual((current["provider"], current["model"]), ("fake", "test-model"))
            result = client.get(f"/api/jobs/{job_id}/sections").json()
            self.assertTrue(result["complete"])
            self.assertEqual(result["result_kind"], "SECTIONS_ONLY")
            self.assertEqual(result["sections"][0]["analysis"]["ideas"][0]["source_segment_ids"], ["seg-1"])
        self.assertEqual(fake.calls, 1)
        self.assertTrue(fake.closed)

    def test_old_queued_job_cannot_go_to_new_provider_after_restart(self):
        journal = SQLiteJobs(self.db)
        journal.initialize()
        original = Transcript("v1", "manual_import", (
            Segment("s1", "Transcript stays private to original provider", 0, 1000),
        ), language="en")
        stale = journal.enqueue(original, provider="old-provider", model="old-model",
                                revision="old-revision", max_chars=12_000)
        fake = FakeAnalysis()
        app = build_app(provider="fake", db_path=self.db, registry={"fake": registration(fake)})
        with TestClient(app) as client:
            for _ in range(100):
                current = client.get(f"/api/jobs/{stale.id}").json()
                if current["state"] == "INTERRUPTED":
                    break
                time.sleep(.01)
            else:
                self.fail("stale job was not interrupted")
            self.assertEqual(current["error_code"], "CONFIGURATION_CHANGED")
            self.assertEqual(client.post(f"/api/jobs/{stale.id}/resume").status_code, 409)
        self.assertEqual(fake.calls, 0)

    def test_cli_explicit_provider_loopback_and_single_worker(self):
        fake = FakeAnalysis()
        directory = Path(self.temp.name) / "private"
        fake_uvicorn = SimpleNamespace(run=Mock())
        with patch("signaltranscript.backend.serve.available_providers", return_value={"fake": registration(fake)}), \
                patch("signaltranscript.backend.serve.build_app") as build, \
                patch.dict("sys.modules", {"uvicorn": fake_uvicorn}):
            original = os.umask(0o077)
            os.umask(original)
            try:
                self.assertEqual(main(["--analysis-provider", "fake", "--data-dir", str(directory),
                                       "--port", "9753"]), 0)
                self.assertEqual(os.umask(original), original)
            finally:
                os.umask(original)
        self.assertEqual(build.call_args.kwargs["provider"], "fake")
        self.assertEqual(build.call_args.kwargs["db_path"], directory / "signaltranscript.db")
        self.assertEqual(fake_uvicorn.run.call_args.kwargs, {
            "host": "127.0.0.1", "port": 9753, "workers": 1, "reload": False,
            "proxy_headers": False, "access_log": False,
        })

    def test_cli_requires_provider_and_rejects_public_directory(self):
        directory = Path(self.temp.name)
        with self.assertRaises(SystemExit) as missing:
            main(["--data-dir", str(directory)])
        self.assertEqual(missing.exception.code, 2)
        directory.chmod(0o755)
        with self.assertRaises(SystemExit) as insecure:
            main(["--analysis-provider", "groq", "--data-dir", str(directory)])
        self.assertEqual(insecure.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
