"""Read-model tests for local library and transcript search."""

from pathlib import Path
import tempfile
import unittest

from signaltranscript.ai.ports import Segment, Transcript
from signaltranscript.backend.jobs import SQLiteJobs
from signaltranscript.backend.library import LibraryReadModel


def transcript(video_id: str, text: str) -> Transcript:
    return Transcript(
        video_id, "manual_import",
        (Segment("s1", text, 0, 1000), Segment("s2", "common tail", 1000, 2000)),
        language="pt",
    )


class LibraryReadModelTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.jobs = SQLiteJobs(Path(self.tmp.name) / "jobs.db")
        self.jobs.initialize()
        self.library = LibraryReadModel(self.jobs)

    def add(self, video_id: str, text: str):
        return self.jobs.enqueue(
            transcript(video_id, text), provider="fake", model="m",
            revision="r1", max_chars=12_000,
        )

    def test_library_groups_versions_and_uses_latest_job(self):
        old = self.add("video-a", "old version")
        other = self.add("video-b", "other")
        latest = self.add("video-a", "new version")
        entries, cursor = self.library.list_entries(limit=10)
        self.assertIsNone(cursor)
        self.assertEqual(
            [(entry.latest_job.id, entry.version_count) for entry in entries],
            [(latest.id, 2), (other.id, 1)],
        )
        self.assertNotEqual(old.id, entries[0].latest_job.id)

    def test_library_pagination_is_stable_by_latest_version_sequence(self):
        a = self.add("a", "a")
        b = self.add("b", "b")
        self.add("a", "a newer")
        c = self.add("c", "c")
        first, cursor = self.library.list_entries(limit=2)
        # Assert by video identity to avoid coupling the test to UUID generation.
        self.assertEqual([entry.latest_job.transcript.video_id for entry in first], ["c", "a"])
        self.assertIsInstance(cursor, int)
        second, next_cursor = self.library.list_entries(limit=2, before=cursor)
        self.assertEqual([entry.latest_job.transcript.video_id for entry in second], ["b"])
        self.assertIsNone(next_cursor)
        self.assertNotIn(a.id, [entry.latest_job.id for entry in second])
        self.assertEqual(b.transcript.video_id, "b")

    def test_search_uses_only_latest_version_and_is_case_insensitive(self):
        self.add("video-a", "LegacyTerm exists only in old version")
        latest = self.add("video-a", "FreshTerm lives here")
        self.add("video-b", "FRESHTERM also appears here")
        old_hits, old_truncated = self.library.search("legacyterm")
        self.assertEqual(old_hits, ())
        self.assertFalse(old_truncated)

        hits, truncated = self.library.search("freshterm")
        self.assertFalse(truncated)
        self.assertEqual([hit.job.transcript.video_id for hit in hits], ["video-b", "video-a"])
        self.assertEqual(hits[-1].job.id, latest.id)
        self.assertTrue(all(hit.segment.id == "s1" for hit in hits))

    def test_search_reports_truncation_and_validates_bounds(self):
        for index in range(3):
            self.add(f"video-{index}", "needle")
        hits, truncated = self.library.search("needle", limit=2)
        self.assertEqual(len(hits), 2)
        self.assertTrue(truncated)
        with self.assertRaises(ValueError):
            self.library.search(" ")
        with self.assertRaises(ValueError):
            self.library.search("needle", limit=51)


if __name__ == "__main__":
    unittest.main()
