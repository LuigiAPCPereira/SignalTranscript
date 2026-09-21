"""A missing completed checkpoint must never be presented as success."""

from pathlib import Path
from contextlib import closing
import sqlite3
import tempfile
import time
import unittest

from fastapi.testclient import TestClient

from signaltranscript.ai.ports import Analysis, Idea, Transcript
from signaltranscript.backend.api import create_app


class Provider:
    async def analyze(self, transcript: Transcript) -> Analysis:
        return Analysis("Section summary", (Idea("Topic", "Explanation", (transcript.segments[0].id,)),),
                        provider="fake", model="model")


class IntegrityTests(unittest.TestCase):
    def test_missing_sections_rejected_even_when_job_says_completed(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "jobs.db"
            app = create_app(database, analysis_provider=Provider(), provider_name="fake",
                             model="model", revision="v1")
            with TestClient(app) as client:
                created = client.post("/api/jobs", json={
                    "video_id": "v1", "source": "manual_import",
                    "segments": [{"id": "s1", "text": "Evidence text", "start_ms": 0, "end_ms": 1000}],
                })
                self.assertEqual(created.status_code, 202)
                job_id = created.json()["id"]
                for _ in range(100):
                    if client.get(f"/api/jobs/{job_id}").json()["state"] == "COMPLETED":
                        break
                    time.sleep(.01)
                else:
                    self.fail("job not completed")
                with closing(sqlite3.connect(database)) as db:
                    with db:
                        db.execute("DELETE FROM analysis_sections WHERE run_id=?", (job_id,))
                self.assertEqual(client.get(f"/api/jobs/{job_id}").status_code, 409)
                self.assertEqual(client.get(f"/api/jobs/{job_id}/sections").status_code, 409)
