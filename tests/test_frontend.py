"""Contract tests for the dependency-free local library frontend."""

from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient

from signaltranscript.ai.ports import Analysis, Idea
from signaltranscript.backend.api import WEB_DIR, create_app


class NeverCalledProvider:
    def __init__(self):
        self.calls = 0

    async def analyze(self, transcript):
        self.calls += 1
        return Analysis(
            "unused",
            (Idea("unused", "unused", (transcript.segments[0].id,)),),
            "fake", "fake-model",
        )


class FrontendContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.provider = NeverCalledProvider()
        self.app = create_app(
            Path(self.tmp.name) / "jobs.db",
            analysis_provider=self.provider,
            provider_name="fake", model="fake-model", revision="r1",
            max_chars=12_000,
        )

    def test_frontend_shell_and_assets_are_same_origin_and_provider_free(self):
        with TestClient(self.app) as client:
            index = client.get("/")
            css = client.get("/assets/app.css")
            js = client.get("/assets/app.js")

        self.assertEqual(index.status_code, 200)
        self.assertTrue(index.headers["content-type"].startswith("text/html"))
        self.assertIn('id="main"', index.text)
        self.assertIn('id="search-form"', index.text)
        self.assertIn('id="reader-segments"', index.text)
        self.assertIn('data-view="sections"', index.text)
        self.assertIn('data-view="synthesis"', index.text)
        self.assertIn('id="reader-knowledge"', index.text)
        self.assertIn('href="/assets/app.css"', index.text)
        self.assertIn('src="/assets/app.js"', index.text)
        self.assertNotIn("http://", index.text)
        self.assertNotIn("https://", index.text)

        self.assertEqual(css.status_code, 200)
        self.assertTrue(css.headers["content-type"].startswith("text/css"))
        self.assertIn("@media(max-width:560px)", css.text)
        self.assertIn("prefers-reduced-motion", css.text)

        self.assertEqual(js.status_code, 200)
        self.assertIn("/api/library", js.text)
        self.assertIn("/api/library/search", js.text)
        self.assertIn("/transcript", js.text)
        self.assertIn("/sections", js.text)
        self.assertIn("/synthesis", js.text)
        self.assertIn("SECTIONS_ONLY", js.text)
        self.assertIn("GLOBAL_SYNTHESIS", js.text)
        self.assertIn("setArtifactAvailability", js.text)
        self.assertIn(".disabled=", js.text)
        self.assertIn("disponibilidade desconhecida", js.text)
        self.assertNotIn('"POST"', js.text)
        self.assertNotIn("'POST'", js.text)
        self.assertNotIn("innerHTML", js.text)
        self.assertNotIn("window.open", js.text)
        self.assertNotIn("location.href", js.text)
        self.assertEqual(self.provider.calls, 0)

    def test_job_metadata_exposes_read_only_artifact_availability(self):
        payload = {
            "video_id": "frontend-fixture",
            "source": "manual_import",
            "language": "pt",
            "segments": [
                {"id": "s1", "text": "conteudo local", "start_ms": 0, "end_ms": 1000},
            ],
        }
        with TestClient(self.app) as client:
            created = client.post("/api/jobs", json=payload)
            self.assertEqual(created.status_code, 202, created.text)
            created_artifacts = created.json()["artifacts"]
            self.assertTrue(created_artifacts["transcript_present"])
            self.assertFalse(created_artifacts["synthesis_present"])
            self.assertIsInstance(created_artifacts["sections_present"], bool)

            current = client.get(f"/api/jobs/{created.json()['id']}")
            self.assertEqual(current.status_code, 200, current.text)
            artifacts = current.json()["artifacts"]
            self.assertTrue(artifacts["transcript_present"])
            self.assertIsInstance(artifacts["sections_present"], bool)
            self.assertIsInstance(artifacts["synthesis_present"], bool)

    def test_packaged_web_files_exist(self):
        for name in ("index.html", "app.css", "app.js"):
            with self.subTest(name=name):
                self.assertTrue((WEB_DIR / name).is_file())


if __name__ == "__main__":
    unittest.main()
