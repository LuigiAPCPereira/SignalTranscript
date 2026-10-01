"""Opt-in local HTTP smoke test. Never contacts a provider without --submit.

The backend, not this CLI, owns provider calls. No automatic job resubmission,
resume, fallback or recording of transcribed text in CLI output.
"""

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

from signaltranscript.ai.coverage import (
    CoverageValidationError, PositionalCoverage, assess_reference_positions,
)
from signaltranscript.ai.ports import Segment, Transcript
from signaltranscript.backend.api import ImportInput
from signaltranscript.backend.caption_evidence import CaptionEvidenceError, parse_manifest

JOB_ID = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")
TERMINAL = {"COMPLETED", "FAILED", "INTERRUPTED", "WAITING_RATE_LIMIT", "CANCELLED"}
MAX_RESPONSE = 512_000


class SmokeFailure(Exception):
    """An operational error safe to show without echoing transcript or keys."""


@dataclass(frozen=True, slots=True)
class SmokeVerification:
    section_count: int
    positional_coverage: PositionalCoverage


@dataclass(frozen=True, slots=True)
class SynthesisVerification:
    idea_count: int
    positional_coverage: PositionalCoverage


def _read_json_file(path: Path, code: str) -> object:
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 512_000:
            raise SmokeFailure(code)
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, TypeError, UnicodeError, OSError):
        raise SmokeFailure(code) from None


def load_fixture(path: Path, evidence_path: Path | None = None) -> tuple[dict[str, object], Transcript]:
    try:
        raw = _read_json_file(path, "INVALID_TRANSCRIPT_FILE")
        payload = ImportInput.model_validate(raw)
        transcript_payload = payload.model_dump(exclude={"evidence"})
        manifest = payload.evidence
        if evidence_path is not None:
            if manifest is not None:
                raise SmokeFailure("DUPLICATE_EVIDENCE_INPUT")
            manifest = _read_json_file(evidence_path, "INVALID_EVIDENCE_FILE")
        if manifest is not None:
            validated = parse_manifest(manifest, transcript_payload)
            payload = ImportInput.model_validate({**transcript_payload, "evidence": asdict(validated)})
        transcript = Transcript(
            video_id=payload.video_id, source=payload.source, language=payload.language,
            segments=tuple(Segment(**item.model_dump()) for item in payload.segments),
        )
    except SmokeFailure:
        raise
    except (CaptionEvidenceError, ValueError, TypeError, UnicodeError):
        raise SmokeFailure("INVALID_TRANSCRIPT_OR_EVIDENCE") from None
    return payload.model_dump(), transcript


def call(base: str, method: str, route: str, body: dict | None = None) -> dict:
    headers = {"Accept": "application/json"}
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(base + route, method=method, data=data, headers=headers)
    opener = build_opener(ProxyHandler({}))
    try:
        with opener.open(request, timeout=8.0) as response:
            expected = {"GET": (200,), "POST": (200, 202)}.get(method)
            if expected is None or response.status not in expected:
                raise SmokeFailure("UNEXPECTED_HTTP_STATUS")
            content = response.read(MAX_RESPONSE + 1)
    except HTTPError as exc:
        raise SmokeFailure(f"HTTP_{exc.code}") from None
    except (URLError, TimeoutError, OSError):
        raise SmokeFailure("TRANSPORT_OUTCOME_UNKNOWN_DO_NOT_RESUBMIT") from None
    if len(content) > MAX_RESPONSE:
        raise SmokeFailure("RESPONSE_TOO_LARGE")
    try:
        result = json.loads(content)
    except (ValueError, UnicodeError):
        raise SmokeFailure("INVALID_HTTP_RESPONSE") from None
    if not isinstance(result, dict):
        raise SmokeFailure("INVALID_HTTP_RESPONSE")
    return result


def verify_provenance(result: dict, expect_evidence: bool) -> None:
    provenance = result.get("provenance")
    if (not isinstance(provenance, dict)
            or provenance.get("evidence_present") is not expect_evidence
            or provenance.get("authorization_status") != "UNVERIFIED"
            or provenance.get("video_identity_status") != "UNVERIFIED"
            or provenance.get("timeline_match_status") != "UNVERIFIED"
            or provenance.get("deep_links_allowed") is not False):
        raise SmokeFailure("INVALID_PROVENANCE_STATE")
    if expect_evidence:
        if provenance.get("evidence_schema") != 2:
            raise SmokeFailure("INVALID_PROVENANCE_STATE")
    elif provenance.get("evidence_schema") is not None:
        raise SmokeFailure("INVALID_PROVENANCE_STATE")


def verify_sections(result: dict, transcript: Transcript, job_id: str, planned: int,
                    provider: str, model: str, expect_evidence: bool = False) -> SmokeVerification:
    verify_provenance(result, expect_evidence)
    sections = result.get("sections")
    if (result.get("job_id") != job_id or result.get("complete") is not True
            or result.get("result_kind") != "SECTIONS_ONLY"
            or result.get("planned_sections") != planned
            or not isinstance(sections, list) or len(sections) != planned):
        raise SmokeFailure("INCOMPLETE_OR_INVALID_SECTIONS")
    section_ids: list[tuple[str, ...]] = []
    references: list[str] = []
    for index, section in enumerate(sections):
        if not isinstance(section, dict) or section.get("index") != index:
            raise SmokeFailure("INVALID_SECTION_ORDER")
        segment_ids = section.get("segment_ids")
        analysis = section.get("analysis")
        if (not isinstance(segment_ids, list) or not segment_ids
                or any(not isinstance(item, str) or not item for item in segment_ids)
                or not isinstance(analysis, dict)
                or not isinstance(analysis.get("summary"), str)
                or not analysis["summary"].strip()
                or not isinstance(analysis.get("ideas"), list)
                or analysis.get("provider") != provider
                or analysis.get("model") != model):
            raise SmokeFailure("INVALID_SECTION_CONTENT")
        allowed = set(segment_ids)
        for idea in analysis["ideas"]:
            if (not isinstance(idea, dict)
                    or not isinstance(idea.get("source_segment_ids"), list)
                    or not idea["source_segment_ids"]
                    or any(ref not in allowed for ref in idea["source_segment_ids"])):
                raise SmokeFailure("INVALID_EVIDENCE_REFERENCES")
            references.extend(idea["source_segment_ids"])
        section_ids.append(tuple(segment_ids))
    try:
        coverage = assess_reference_positions(transcript, section_ids, references)
    except CoverageValidationError as exc:
        if exc.code == "SECTION_COVERAGE_MISMATCH":
            raise SmokeFailure("INCOMPLETE_SEGMENT_COVERAGE") from None
        raise SmokeFailure(f"INVALID_POSITIONAL_EVIDENCE_{exc.code}") from None
    return SmokeVerification(len(sections), coverage)



def verify_global_synthesis(
    result: dict, transcript: Transcript, job_id: str, provider: str, model: str,
    expect_evidence: bool = False,
) -> SynthesisVerification:
    """Validate the separate global result without trusting server-side claims."""
    verify_provenance(result, expect_evidence)
    analysis = result.get("analysis")
    coverage_payload = result.get("coverage")
    if (result.get("job_id") != job_id
            or result.get("result_kind") != "GLOBAL_SYNTHESIS"
            or not isinstance(analysis, dict)
            or not isinstance(analysis.get("summary"), str)
            or not analysis["summary"].strip()
            or not isinstance(analysis.get("ideas"), list)
            or analysis.get("provider") != provider
            or analysis.get("model") != model
            or not isinstance(coverage_payload, dict)):
        raise SmokeFailure("INVALID_GLOBAL_SYNTHESIS")

    transcript_ids = tuple(segment.id for segment in transcript.segments)
    allowed = set(transcript_ids)
    references: list[str] = []
    for idea in analysis["ideas"]:
        if (not isinstance(idea, dict)
                or not isinstance(idea.get("title"), str)
                or not idea["title"].strip()
                or not isinstance(idea.get("explanation"), str)
                or not idea["explanation"].strip()
                or not isinstance(idea.get("source_segment_ids"), list)
                or not idea["source_segment_ids"]
                or any(not isinstance(ref, str) or ref not in allowed
                       for ref in idea["source_segment_ids"])
                or len(set(idea["source_segment_ids"])) != len(idea["source_segment_ids"])):
            raise SmokeFailure("INVALID_GLOBAL_SYNTHESIS_EVIDENCE")
        references.extend(idea["source_segment_ids"])

    try:
        expected_coverage = assess_reference_positions(
            transcript, (transcript_ids,), references,
        )
    except CoverageValidationError as exc:
        raise SmokeFailure(f"INVALID_GLOBAL_SYNTHESIS_EVIDENCE_{exc.code}") from None
    if coverage_payload != asdict(expected_coverage):
        raise SmokeFailure("INVALID_GLOBAL_SYNTHESIS_COVERAGE")
    return SynthesisVerification(len(analysis["ideas"]), expected_coverage)


def _synthesis_configuration(base: str, provider: str, request) -> tuple[dict, str]:
    configuration = request(base, "GET", "/api/config")
    if (configuration.get("synthesis_provider") != provider
            or not isinstance(configuration.get("synthesis_model"), str)
            or not configuration["synthesis_model"].strip()):
        raise SmokeFailure("SYNTHESIS_PROVIDER_CONFIGURATION_MISMATCH")
    return configuration, configuration["synthesis_model"]


def execute_synthesis(
    *, port: int, job_id: str, transcript: Transcript, provider: str,
    expect_evidence: bool = False, request=call,
) -> SynthesisVerification:
    """Run exactly one explicit synthesis request after verifying local configuration."""
    base = f"http://127.0.0.1:{port}"
    _, model = _synthesis_configuration(base, provider, request)
    result = request(base, "POST", f"/api/jobs/{job_id}/synthesis")
    return verify_global_synthesis(
        result, transcript, job_id, provider, model, expect_evidence,
    )


def read_synthesis(
    *, port: int, job_id: str, transcript: Transcript, provider: str,
    expect_evidence: bool = False, request=None,
) -> SynthesisVerification:
    """Read historical checkpoint using one GET; current synthesis config is irrelevant."""
    request = call if request is None else request
    base = f"http://127.0.0.1:{port}"
    result = request(base, "GET", f"/api/jobs/{job_id}/synthesis")
    analysis = result.get("analysis")
    if (not isinstance(analysis, dict)
            or analysis.get("provider") != provider
            or not isinstance(analysis.get("model"), str)
            or not analysis["model"].strip()):
        raise SmokeFailure("SYNTHESIS_PROVIDER_CONFIGURATION_MISMATCH")
    return verify_global_synthesis(
        result, transcript, job_id, provider, analysis["model"], expect_evidence,
    )


def execute(*, port: int, provider: str, payload: dict, transcript: Transcript,
            max_wait_seconds: int, request=call, pause=time.sleep) -> tuple[str, SmokeVerification]:
    base = f"http://127.0.0.1:{port}"
    configuration = request(base, "GET", "/api/config")
    if (configuration.get("analysis_provider") != provider
            or not isinstance(configuration.get("model"), str)
            or not configuration["model"].strip()
            or configuration.get("result_kind") != "SECTIONS_ONLY"):
        raise SmokeFailure("PROVIDER_CONFIGURATION_MISMATCH")
    expect_evidence = payload.get("evidence") is not None
    created = request(base, "POST", "/api/jobs", payload)
    verify_provenance(created, expect_evidence)
    job_id = created.get("id")
    if not isinstance(job_id, str) or JOB_ID.fullmatch(job_id) is None:
        raise SmokeFailure("UNKNOWN_SUBMISSION_OUTCOME_DO_NOT_RESUBMIT")
    print(f"Job registrado: {job_id}. Não submeta novamente se houver timeout.")
    deadline = time.monotonic() + max_wait_seconds
    while True:
        job = request(base, "GET", f"/api/jobs/{job_id}")
        if job.get("id") != job_id:
            raise SmokeFailure("INVALID_JOB_RESPONSE")
        verify_provenance(job, expect_evidence)
        state = job.get("state")
        if state in TERMINAL:
            break
        if state not in ("QUEUED", "RUNNING"):
            raise SmokeFailure("UNKNOWN_JOB_STATE")
        if time.monotonic() >= deadline:
            raise SmokeFailure(f"POLL_TIMEOUT_JOB_{job_id}_DO_NOT_RESUBMIT")
        pause(0.5)
    if state != "COMPLETED":
        raise SmokeFailure(f"JOB_{state}_CHECK_STATUS_{job_id}")
    planned = job.get("planned_sections")
    if type(planned) is not int or not 1 <= planned <= 64:
        raise SmokeFailure("INVALID_SECTION_COUNT")
    sections = request(base, "GET", f"/api/jobs/{job_id}/sections")
    return job_id, verify_sections(sections, transcript, job_id, planned,
                                   provider, configuration["model"], expect_evidence)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local smoke test with separate AI-operation consent")
    parser.add_argument("--transcript", type=Path, required=True)
    parser.add_argument("--evidence", type=Path,
                        help="Optional local caption-evidence sidecar; validated before any HTTP")
    parser.add_argument("--submit-analysis", "--submit", dest="submit_analysis", action="store_true",
                        help="Allow ONE section-analysis job submission")
    parser.add_argument("--confirm-analysis-upload", "--confirm-provider-upload",
                        dest="confirm_analysis_upload", action="store_true",
                        help="Acknowledge section analysis may send transcript data and consume quota")
    parser.add_argument("--expect-analysis-provider", "--expect-provider",
                        dest="expect_analysis_provider",
                        help="Section-analysis provider configured on the local server")
    parser.add_argument("--synthesize-global", action="store_true",
                        help="After sections complete, allow ONE explicit global-synthesis POST")
    parser.add_argument("--check-synthesis-job",
                        help="Read an already persisted synthesis by job ID using GET only")
    parser.add_argument("--confirm-synthesis-upload", action="store_true",
                        help="Separately acknowledge synthesis may send data and consume additional quota")
    parser.add_argument("--expect-synthesis-provider",
                        help="Global-synthesis provider configured on the local server")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--max-wait-seconds", type=int, default=180)
    args = parser.parse_args(argv)
    try:
        payload, transcript = load_fixture(args.transcript, args.evidence)
        has_evidence = payload.get("evidence") is not None
        print(f"Pré-validação local: {len(transcript.segments)} segmentos; nenhum texto exibido.")
        if has_evidence:
            print("Manifesto de proveniência validado localmente; vídeo/sincronização continuam NÃO verificados.")

        check_mode = args.check_synthesis_job is not None
        if check_mode:
            if (not JOB_ID.fullmatch(args.check_synthesis_job)
                    or not args.expect_synthesis_provider
                    or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}",
                                        args.expect_synthesis_provider)
                    or args.submit_analysis or args.confirm_analysis_upload
                    or args.expect_analysis_provider or args.synthesize_global
                    or args.confirm_synthesis_upload
                    or not 1 <= args.port <= 65535):
                raise SmokeFailure("INVALID_SYNTHESIS_CHECK_OPTIONS")
            verification = read_synthesis(
                port=args.port, job_id=args.check_synthesis_job,
                transcript=transcript, provider=args.expect_synthesis_provider,
                expect_evidence=has_evidence,
            )
            coverage = verification.positional_coverage
            print(
                f"Checkpoint GLOBAL_SYNTHESIS encontrado para job {args.check_synthesis_job}: "
                f"{verification.idea_count} ideia(s); "
                f"início={'sim' if coverage.beginning_referenced else 'não'}, "
                f"meio={'sim' if coverage.middle_referenced else 'não'}, "
                f"fim={'sim' if coverage.end_referenced else 'não'}."
            )
            print("Consulta somente leitura; nenhuma nova inferência foi solicitada.")
            return 0

        synthesis_options_used = bool(
            args.synthesize_global or args.confirm_synthesis_upload
            or args.expect_synthesis_provider
        )
        if not args.submit_analysis:
            if (args.confirm_analysis_upload or args.expect_analysis_provider
                    or synthesis_options_used):
                raise SmokeFailure("ANALYSIS_SUBMISSION_FLAG_REQUIRED")
            print("Somente validação local; nenhuma requisição HTTP ou IA.")
            return 0

        if (not args.confirm_analysis_upload or not args.expect_analysis_provider
                or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", args.expect_analysis_provider)
                or not 1 <= args.port <= 65535
                or not 1 <= args.max_wait_seconds <= 3600):
            raise SmokeFailure("INVALID_EXPLICIT_ANALYSIS_OPTIONS")

        if args.synthesize_global:
            if (not args.confirm_synthesis_upload or not args.expect_synthesis_provider
                    or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}",
                                        args.expect_synthesis_provider)):
                raise SmokeFailure("INVALID_EXPLICIT_SYNTHESIS_OPTIONS")
        elif args.confirm_synthesis_upload or args.expect_synthesis_provider:
            raise SmokeFailure("SYNTHESIS_FLAG_REQUIRED")

        job_id, verification = execute(
            port=args.port, provider=args.expect_analysis_provider,
            payload=payload, transcript=transcript,
            max_wait_seconds=args.max_wait_seconds,
        )
        print(f"Análise por seções concluída: {verification.section_count} seção(ões); job {job_id}.")
        coverage = verification.positional_coverage
        print("Cobertura posicional das referências das seções: "
              f"início={'sim' if coverage.beginning_referenced else 'não'}, "
              f"meio={'sim' if coverage.middle_referenced else 'não'}, "
              f"fim={'sim' if coverage.end_referenced else 'não'}; "
              f"{coverage.referenced_segments}/{coverage.total_segments} segmentos referenciados.")
        print("Resultado SECTIONS_ONLY; isso não é síntese global, prova semântica, factualidade ou deep link.")

        if args.synthesize_global:
            print("Síntese global autorizada separadamente: esta é uma SEGUNDA operação e pode consumir cota adicional.")
            synthesis = execute_synthesis(
                port=args.port, job_id=job_id, transcript=transcript,
                provider=args.expect_synthesis_provider, expect_evidence=has_evidence,
            )
            global_coverage = synthesis.positional_coverage
            print(
                "GLOBAL_SYNTHESIS concluída: "
                f"{synthesis.idea_count} ideia(s); cobertura das referências "
                f"início={'sim' if global_coverage.beginning_referenced else 'não'}, "
                f"meio={'sim' if global_coverage.middle_referenced else 'não'}, "
                f"fim={'sim' if global_coverage.end_referenced else 'não'}."
            )
            print("Síntese global continua sendo descrição do conteúdo, não verificação factual ou autorização de deep link.")
        return 0
    except SmokeFailure as exc:
        print(f"Smoke test: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
