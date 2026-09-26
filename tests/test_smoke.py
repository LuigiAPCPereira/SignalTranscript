"""Offline smoke workflow tests; never import Groq SDK or access external APIs."""

from pathlib import Path
import json
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from signaltranscript.ai.ports import Analysis, Idea, Segment, Transcript
from signaltranscript.backend.caption_evidence import canonical_transcript_sha256
from signaltranscript.backend.serve import (
    AnalysisRegistration, SynthesisRegistration, build_app,
)
from signaltranscript.backend.smoke import (
    SmokeFailure, execute, execute_synthesis, load_fixture, main, read_synthesis,
    verify_global_synthesis, verify_sections,
)


def provenance(evidence: bool = False) -> dict:
    return {"evidence_present": evidence, "evidence_schema": 2 if evidence else None,
            "authorization_status": "UNVERIFIED", "video_identity_status": "UNVERIFIED",
            "timeline_match_status": "UNVERIFIED", "deep_links_allowed": False}


class FakeSynthesis:
    def __init__(self):
        self.calls = 0

    async def synthesize(self, transcript: Transcript, sectioned) -> Analysis:
        self.calls += 1
        refs = tuple(segment.id for segment in transcript.segments)
        return Analysis(
            "Síntese global sintética.",
            (Idea("Global", "Evidência estrutural.", refs),),
            provider="synth-fake", model="synth-model",
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

    def test_evidence_sidecar_is_validated_before_http_and_reaches_backend(self):
        manifest = Path(self.tmp.name) / "evidence.json"
        record = {"schema_version": 2, "source_kind": "user_supplied_caption",
                  "caption_format": "srt", "caption_sha256": "a" * 64,
                  "transcript_sha256": "b" * 64,
                  "transcript_content_sha256": canonical_transcript_sha256({k: v for k, v in self.payload.items() if k != "evidence"}),
                  "declared_video_id": "synthetic", "authorization_status": "UNVERIFIED",
                  "video_identity_status": "UNVERIFIED", "timeline_match_status": "UNVERIFIED",
                  "deep_links_allowed": False}
        manifest.write_text(json.dumps(record))
        payload, transcript = load_fixture(self.path, manifest)
        self.assertEqual(payload["evidence"], record)

        fake = FakeAnalysis()
        app = build_app(provider="fake", db_path=Path(self.tmp.name) / "evidence.db", registry={"fake":
            AnalysisRegistration("fake", "example-model", "example-v1", 12_000, lambda: fake)})
        with TestClient(app) as client:
            def request(base, method, route, body=None):
                response = client.request(method, route, json=body)
                self.assertIn(response.status_code, (200, 202), response.text)
                return response.json()
            job_id, verification = execute(port=8765, provider="fake", payload=payload,
                                           transcript=transcript, max_wait_seconds=10,
                                           request=request, pause=lambda _: time.sleep(.01))
            self.assertTrue(job_id)
            self.assertEqual(verification.section_count, 1)
        self.assertEqual(fake.calls, 1)

        changed = json.loads(self.path.read_text())
        changed["segments"][0]["text"] = "Alterado"
        self.path.write_text(json.dumps(changed))
        with self.assertRaisesRegex(SmokeFailure, "INVALID_TRANSCRIPT_OR_EVIDENCE"):
            load_fixture(self.path, manifest)

    def test_submit_requires_explicit_acknowledgment(self):
        with patch("signaltranscript.backend.smoke.call") as network:
            self.assertEqual(main(["--transcript", str(self.path), "--submit",
                                   "--expect-provider", "groq"]), 2)
            network.assert_not_called()


    def test_synthesis_requires_second_consent_before_any_http(self):
        with patch("signaltranscript.backend.smoke.call") as network:
            self.assertEqual(main([
                "--transcript", str(self.path),
                "--submit-analysis", "--confirm-analysis-upload",
                "--expect-analysis-provider", "fake",
                "--synthesize-global", "--expect-synthesis-provider", "synth-fake",
            ]), 2)
            network.assert_not_called()

    def test_synthesis_options_without_synthesis_flag_fail_before_analysis(self):
        with patch("signaltranscript.backend.smoke.call") as network:
            self.assertEqual(main([
                "--transcript", str(self.path),
                "--submit-analysis", "--confirm-analysis-upload",
                "--expect-analysis-provider", "fake",
                "--confirm-synthesis-upload", "--expect-synthesis-provider", "synth-fake",
            ]), 2)
            network.assert_not_called()

    def test_wrong_synthesis_provider_blocks_second_post(self):
        request = Mock(return_value={
            "analysis_provider": "fake", "model": "example-model",
            "result_kind": "SECTIONS_ONLY",
            "synthesis_provider": "synth-fake", "synthesis_model": "synth-model",
        })
        with self.assertRaisesRegex(SmokeFailure, "SYNTHESIS_PROVIDER_CONFIGURATION_MISMATCH"):
            execute_synthesis(
                port=8765, job_id="job-1", transcript=self.transcript,
                provider="other", request=request,
            )
        self.assertEqual(request.call_count, 1)
        self.assertEqual(request.call_args.args[1:3], ("GET", "/api/config"))

    def test_global_synthesis_verifier_recomputes_coverage(self):
        result = {
            "job_id": "job-1",
            "result_kind": "GLOBAL_SYNTHESIS",
            "analysis": {
                "summary": "Resumo global",
                "ideas": [{
                    "title": "Tema", "explanation": "Explicação",
                    "source_segment_ids": ["s1"],
                }],
                "provider": "synth-fake", "model": "synth-model",
            },
            "coverage": {
                "total_segments": 1, "referenced_segments": 1,
                "beginning_referenced": True, "middle_referenced": False,
                "end_referenced": False,
            },
            "provenance": provenance(),
        }
        verified = verify_global_synthesis(
            result, self.transcript, "job-1", "synth-fake", "synth-model",
        )
        self.assertEqual(verified.idea_count, 1)
        self.assertEqual(verified.positional_coverage.referenced_segments, 1)
        result["coverage"]["referenced_segments"] = 0
        with self.assertRaisesRegex(SmokeFailure, "INVALID_GLOBAL_SYNTHESIS_COVERAGE"):
            verify_global_synthesis(
                result, self.transcript, "job-1", "synth-fake", "synth-model",
            )


    def test_read_synthesis_uses_get_only_and_revalidates_configuration(self):
        calls = iter([
            {
                "analysis_provider": "fake", "model": "example-model",
                "result_kind": "SECTIONS_ONLY",
                "synthesis_provider": "synth-fake", "synthesis_model": "synth-model",
            },
            {
                "job_id": "job-1",
                "result_kind": "GLOBAL_SYNTHESIS",
                "analysis": {
                    "summary": "Resumo global",
                    "ideas": [{
                        "title": "Tema", "explanation": "Explicação",
                        "source_segment_ids": ["s1"],
                    }],
                    "provider": "synth-fake", "model": "synth-model",
                },
                "coverage": {
                    "total_segments": 1, "referenced_segments": 1,
                    "beginning_referenced": True, "middle_referenced": False,
                    "end_referenced": False,
                },
                "provenance": provenance(),
            },
        ])
        request = Mock(side_effect=lambda *args: next(calls))
        verified = read_synthesis(
            port=8765, job_id="job-1", transcript=self.transcript,
            provider="synth-fake", request=request,
        )
        self.assertEqual(verified.idea_count, 1)
        self.assertEqual([call.args[1] for call in request.call_args_list], ["GET", "GET"])

    def test_cli_check_synthesis_requires_no_upload_consent_and_never_posts(self):
        result = {
            "job_id": "job-1",
            "result_kind": "GLOBAL_SYNTHESIS",
            "analysis": {
                "summary": "Resumo global",
                "ideas": [{
                    "title": "Tema", "explanation": "Explicação",
                    "source_segment_ids": ["s1"],
                }],
                "provider": "synth-fake", "model": "synth-model",
            },
            "coverage": {
                "total_segments": 1, "referenced_segments": 1,
                "beginning_referenced": True, "middle_referenced": False,
                "end_referenced": False,
            },
            "provenance": provenance(),
        }
        with patch("signaltranscript.backend.smoke.call") as request:
            request.side_effect = [
                {
                    "analysis_provider": "fake", "model": "example-model",
                    "result_kind": "SECTIONS_ONLY",
                    "synthesis_provider": "synth-fake", "synthesis_model": "synth-model",
                },
                result,
            ]
            self.assertEqual(main([
                "--transcript", str(self.path),
                "--check-synthesis-job", "job-1",
                "--expect-synthesis-provider", "synth-fake",
            ]), 0)
            self.assertEqual([call.args[1] for call in request.call_args_list], ["GET", "GET"])

    def test_bad_transcript_rejected_offline(self):
        self.path.write_text('''{"video_id":"synthetic", "source":"manual_import",
          "segments":[{"id":"s1", "text":"A", "start_ms":0,"end_ms":1},
                      {"id":"s1", "text":"B", "start_ms":1,"end_ms":2}]}''')
        with self.assertRaisesRegex(SmokeFailure, "INVALID_TRANSCRIPT_OR_EVIDENCE"):
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
            {"id": "job-1", "provenance": provenance()},
            {"id": "job-1", "state":"RUNNING", "provenance": provenance()},
        ])
        request = Mock(side_effect=lambda *args: next(calls))
        with patch("signaltranscript.backend.smoke.time.monotonic", return_value=100.0):
            with self.assertRaisesRegex(SmokeFailure, "DO_NOT_RESUBMIT"):
                execute(port=8765, provider="fake", payload=self.payload,
                        transcript=self.transcript, max_wait_seconds=0, request=request)
        self.assertEqual(sum(call.args[1] == "POST" for call in request.call_args_list), 1)

    def test_citation_and_missing_coverage_are_rejected(self):
        section = {"index": 0, "segment_ids": ["s1"],
                   "analysis":{"summary":"sum", "ideas":[{"source_segment_ids":["unknown"]}],
                               "provider":"fake", "model":"example-model"}}
        result = {"job_id":"job-1", "complete":True, "result_kind":"SECTIONS_ONLY",
                  "planned_sections":1, "sections":[section], "provenance": provenance()}
        with self.assertRaisesRegex(SmokeFailure, "INVALID_EVIDENCE"):
            verify_sections(result, self.transcript, "job-1", 1, "fake", "example-model")
        section["analysis"]["ideas"] = []
        section["segment_ids"] = ["different"]
        with self.assertRaisesRegex(SmokeFailure, "INCOMPLETE_SEGMENT_COVERAGE"):
            verify_sections(result, self.transcript, "job-1", 1, "fake", "example-model")

    def test_verification_reports_reference_positions_without_promoting_summary(self):
        source = Transcript(
            video_id="synthetic", source="manual_import", language="pt",
            segments=tuple(Segment(f"s{i}", f"texto {i}", i, i + 1) for i in range(9)),
        )
        sections = []
        for index, ids, refs in (
            (0, ["s0", "s1", "s2"], ["s0"]),
            (1, ["s3", "s4", "s5"], ["s4"]),
            (2, ["s6", "s7", "s8"], ["s8"]),
        ):
            sections.append({"index": index, "segment_ids": ids,
                             "analysis": {"summary": f"sum {index}",
                                          "ideas": [{"source_segment_ids": refs}],
                                          "provider": "fake", "model": "example-model"}})
        result = {"job_id": "job-1", "complete": True, "result_kind": "SECTIONS_ONLY",
                  "planned_sections": 3, "sections": sections, "provenance": provenance()}

        verification = verify_sections(result, source, "job-1", 3, "fake", "example-model")

        self.assertEqual(verification.section_count, 3)
        self.assertTrue(verification.positional_coverage.spans_all_positions)
        self.assertEqual(verification.positional_coverage.referenced_segments, 3)


    def test_end_to_end_http_with_separate_fake_analysis_and_synthesis(self):
        analysis = FakeAnalysis()
        synthesis = FakeSynthesis()
        db_path = Path(self.tmp.name) / "two-stage.db"
        app = build_app(
            provider="fake", db_path=db_path,
            registry={"fake": AnalysisRegistration(
                "fake", "example-model", "example-v1", 12_000, lambda: analysis,
            )},
            synthesis_provider="synth-fake",
            synthesis_registry={"synth-fake": SynthesisRegistration(
                "synth-fake", "synth-model", "synth-v1", lambda: synthesis,
            )},
        )
        with TestClient(app) as client:
            def request(base, method, route, body=None):
                response = client.request(method, route, json=body)
                self.assertIn(response.status_code, (200, 202), response.text)
                return response.json()

            job_id, section_verification = execute(
                port=8765, provider="fake", payload=self.payload,
                transcript=self.transcript, max_wait_seconds=10,
                request=request, pause=lambda _: time.sleep(.01),
            )
            global_verification = execute_synthesis(
                port=8765, job_id=job_id, transcript=self.transcript,
                provider="synth-fake", request=request,
            )
            self.assertEqual(section_verification.section_count, 1)
            self.assertEqual(global_verification.idea_count, 1)
        self.assertEqual(analysis.calls, 1)
        self.assertEqual(synthesis.calls, 1)

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
            job_id, verification = execute(port=8765, provider="fake", payload=self.payload,
                                           transcript=self.transcript, max_wait_seconds=10,
                                           request=request, pause=lambda _: time.sleep(.01))
            self.assertEqual(verification.section_count, 1)
            self.assertFalse(verification.positional_coverage.spans_all_positions)
            self.assertTrue(job_id)
            self.assertEqual(fake.calls, 1)


if __name__ == "__main__":
    unittest.main()
