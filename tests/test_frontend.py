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
        self.assertNotIn("innerHTML", js.text)
        self.assertNotIn("window.open", js.text)
        self.assertNotIn("location.href", js.text)
        self.assertEqual(self.provider.calls, 0)

    def test_packaged_web_files_exist(self):
        for name in ("index.html", "app.css", "app.js"):
            with self.subTest(name=name):
                self.assertTrue((WEB_DIR / name).is_file())


if __name__ == "__main__":
    unittest.main()
