"""Opt-in local HTTP smoke test. Never contacts a provider without --submit.

The backend, not this CLI, owns provider calls. No automatic job resubmission,
resume, fallback or recording of transcribed text in CLI output.
"""

import argparse
import json
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

from signaltranscript.ai.ports import Segment, Transcript
from signaltranscript.backend.api import ImportInput

JOB_ID = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")
TERMINAL = {"COMPLETED", "FAILED", "INTERRUPTED", "WAITING_RATE_LIMIT", "CANCELLED"}
MAX_RESPONSE = 512_000


class SmokeFailure(Exception):
    """An operational error safe to show without echoing transcript or keys."""


def load_fixture(path: Path) -> tuple[dict[str, object], Transcript]:
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 512_000:
            raise SmokeFailure("INVALID_TRANSCRIPT_FILE")
        raw = json.loads(path.read_text(encoding="utf-8"))
        # Reuse the exact HTTP input boundary, not a second homegrown schema.
        payload = ImportInput.model_validate(raw)
        transcript = Transcript(
            video_id=payload.video_id, source=payload.source, language=payload.language,
            segments=tuple(Segment(**item.model_dump()) for item in payload.segments),
        )
    except (ValueError, TypeError, UnicodeError):
        raise SmokeFailure("INVALID_TRANSCRIPT") from None
    except OSError:
        raise SmokeFailure("INVALID_TRANSCRIPT_FILE") from None
    return payload.model_dump(), transcript


def call(base: str, method: str, route: str, body: dict | None = None) -> dict:
    headers = {"Accept": "application/json"}
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(base + route, method=method, data=data, headers=headers)
    # The only permitted host is an explicit numeric loopback. Never honor proxies.
    opener = build_opener(ProxyHandler({}))
    try:
        with opener.open(request, timeout=8.0) as response:
            if response.status not in ({"GET": (200,), "POST": (202,)}[method]):
                raise SmokeFailure("UNEXPECTED_HTTP_STATUS")
            content = response.read(MAX_RESPONSE + 1)
    except HTTPError as exc:
        raise SmokeFailure(f"HTTP_{exc.code}") from None
    except (URLError, TimeoutError, OSError):
        # POST may have been accepted despite a transport error. Never submit again.
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


def verify_sections(result: dict, transcript: Transcript, job_id: str, planned: int,
                    provider: str, model: str) -> int:
    sections = result.get("sections")
    if (result.get("job_id") != job_id or result.get("complete") is not True
            or result.get("result_kind") != "SECTIONS_ONLY"
            or result.get("planned_sections") != planned
            or not isinstance(sections, list) or len(sections) != planned):
        raise SmokeFailure("INCOMPLETE_OR_INVALID_SECTIONS")
    expected = [segment.id for segment in transcript.segments]
    covered: list[str] = []
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
        covered.extend(segment_ids)
    if covered != expected:
        raise SmokeFailure("INCOMPLETE_SEGMENT_COVERAGE")
    return len(sections)


def execute(*, port: int, provider: str, payload: dict, transcript: Transcript,
            max_wait_seconds: int, request=call, pause=time.sleep) -> tuple[str, int]:
    base = f"http://127.0.0.1:{port}"
    configuration = request(base, "GET", "/api/config")
    if (configuration.get("analysis_provider") != provider
            or not isinstance(configuration.get("model"), str)
            or not configuration["model"].strip()
            or configuration.get("result_kind") != "SECTIONS_ONLY"):
        raise SmokeFailure("PROVIDER_CONFIGURATION_MISMATCH")
    created = request(base, "POST", "/api/jobs", payload)
    job_id = created.get("id")
    if not isinstance(job_id, str) or JOB_ID.fullmatch(job_id) is None:
        raise SmokeFailure("UNKNOWN_SUBMISSION_OUTCOME_DO_NOT_RESUBMIT")
    print(f"Job registrado: {job_id}. Não submeta novamente se houver timeout.")
    deadline = time.monotonic() + max_wait_seconds
    while True:
        job = request(base, "GET", f"/api/jobs/{job_id}")
        if job.get("id") != job_id:
            raise SmokeFailure("INVALID_JOB_RESPONSE")
        state = job.get("state")
        if state in TERMINAL:
            break
        if state not in ("QUEUED", "RUNNING"):
            raise SmokeFailure("UNKNOWN_JOB_STATE")
        if time.monotonic() >= deadline:
            raise SmokeFailure(f"POLL_TIMEOUT_JOB_{job_id}_DO_NOT_RESUBMIT")
        pause(0.5)
    if state != "COMPLETED":
        # Safe machine code only, never raw provider response.
        raise SmokeFailure(f"JOB_{state}_CHECK_STATUS_{job_id}")
    planned = job.get("planned_sections")
    if type(planned) is not int or not 1 <= planned <= 64:
        raise SmokeFailure("INVALID_SECTION_COUNT")
    sections = request(base, "GET", f"/api/jobs/{job_id}/sections")
    return job_id, verify_sections(sections, transcript, job_id, planned,
                                   provider, configuration["model"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local, explicit analysis smoke test")
    parser.add_argument("--transcript", type=Path, required=True)
    parser.add_argument("--submit", action="store_true", help="Allow ONE job submission to selected provider")
    parser.add_argument("--confirm-provider-upload", action="store_true",
                        help="Acknowledge the transcript may leave your computer and consume quota")
    parser.add_argument("--expect-provider", help="Provider configured on the local server")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--max-wait-seconds", type=int, default=180)
    args = parser.parse_args(argv)
    try:
        payload, transcript = load_fixture(args.transcript)
        print(f"Pré-validação local: {len(transcript.segments)} segmentos; nenhum texto exibido.")
        if not args.submit:
            if args.confirm_provider_upload or args.expect_provider:
                raise SmokeFailure("SUBMISSION_FLAG_REQUIRED")
            print("Somente validação local; nenhuma requisição HTTP ou IA.")
            return 0
        if (not args.confirm_provider_upload or not args.expect_provider
                or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", args.expect_provider)
                or not 1 <= args.port <= 65535
                or not 1 <= args.max_wait_seconds <= 3600):
            raise SmokeFailure("INVALID_EXPLICIT_SUBMISSION_OPTIONS")
        job_id, count = execute(port=args.port, provider=args.expect_provider,
                                payload=payload, transcript=transcript,
                                max_wait_seconds=args.max_wait_seconds)
        print(f"Concluído: {count} seção(ões) com cobertura estrutural dos segmentos; job {job_id}.")
        print("Resultado SECTIONS_ONLY; veracidade e síntese global não comprovadas.")
        return 0
    except SmokeFailure as exc:
        print(f"Smoke test: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
