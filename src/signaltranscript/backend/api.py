"""Local HTTP shell for imported-transcript analysis, not a public server.

The app factory requires a chosen provider. There is no default Groq key,
implicit provider switch, network acquisition, or hidden retry.
"""

import asyncio
from contextlib import asynccontextmanager
from collections.abc import Awaitable, Callable
from dataclasses import asdict
import fcntl
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from signaltranscript.ai.errors import ProviderFailure
from signaltranscript.ai.long_form import ChunkPlanningError, SectionedAnalysis
from signaltranscript.ai.ports import AnalysisProvider, Segment, Transcript
from signaltranscript.ai.section_checkpoint import (
    CheckpointMismatch, SQLiteSectionCheckpoint, analyze_with_checkpoint,
)
from signaltranscript.ai.synthesis import GlobalSynthesisProvider, SynthesisValidationError
from signaltranscript.ai.synthesis_checkpoint import (
    SQLiteGlobalSynthesisCheckpoint, SynthesisCheckpointMismatch,
    synthesize_with_checkpoint,
)
from signaltranscript.backend.caption_evidence import (
    CaptionEvidenceError, parse_manifest, verify_submitted_caption,
)
from signaltranscript.backend.caption_import import MAX_BYTES
from signaltranscript.backend.jobs import Job, JobConflict, SQLiteJobs, safe_code


class SegmentInput(BaseModel):
    id: str = Field(min_length=1, max_length=256)
    text: str = Field(min_length=1, max_length=12_000)
    start_ms: int | None = None
    end_ms: int | None = None


class CaptionVerificationInput(BaseModel):
    format: str = Field(pattern="^(srt|vtt)$")
    text: str = Field(min_length=1, max_length=MAX_BYTES)


class ImportInput(BaseModel):
    video_id: str = Field(min_length=1, max_length=256)
    source: str = Field(min_length=1, max_length=256)
    language: str | None = Field(default=None, max_length=64)
    segments: list[SegmentInput] = Field(min_length=1, max_length=4_096)
    evidence: dict[str, object] | None = None
    # Transport-only verification material must never become part of the
    # canonical transcript model/hash when callers use model_dump().
    caption_verification: CaptionVerificationInput | None = Field(default=None, exclude=True)


def provenance_view(job: Job) -> dict[str, object]:
    evidence = job.evidence
    return {
        "evidence_present": evidence is not None,
        "evidence_schema": evidence.schema_version if evidence is not None else None,
        "authorization_status": evidence.authorization_status if evidence is not None else "UNVERIFIED",
        "video_identity_status": evidence.video_identity_status if evidence is not None else "UNVERIFIED",
        "timeline_match_status": evidence.timeline_match_status if evidence is not None else "UNVERIFIED",
        "deep_links_allowed": False,
    }


def view(jobs: SQLiteJobs, job: Job) -> dict[str, object]:
    completed = jobs.completed_sections(job.id)
    if job.state == "COMPLETED" and completed != job.section_count:
        raise HTTPException(status_code=409, detail="INVALID_CHECKPOINT")
    return {"id": job.id, "video_id": job.transcript.video_id, "state": job.state,
            "provider": job.provider, "model": job.model, "attempts": job.attempts,
            "planned_sections": job.section_count,
            "completed_sections": completed, "error_code": job.error_code,
            "result_kind": "SECTIONS_ONLY" if job.state == "COMPLETED" else None,
            "provenance": provenance_view(job)}


def create_app(db_path: Path, *, analysis_provider: AnalysisProvider, provider_name: str,
               model: str, revision: str, max_chars: int = 12_000,
               on_provider_shutdown: Callable[[], Awaitable[None]] | None = None,
               synthesis_provider: GlobalSynthesisProvider | None = None,
               synthesis_provider_name: str | None = None,
               synthesis_model: str | None = None,
               synthesis_revision: str | None = None,
               on_synthesis_provider_shutdown: Callable[[], Awaitable[None]] | None = None) -> FastAPI:
    """One Linux process, one section worker; global synthesis is explicit opt-in."""
    if any(not isinstance(v, str) or not v.strip() for v in (provider_name, model, revision)):
        raise ValueError("provider, model and revision are required")
    if type(max_chars) is not int or max_chars <= 0:
        raise ValueError("max_chars must be a positive integer")
    synthesis_identity = (synthesis_provider_name, synthesis_model, synthesis_revision)
    if synthesis_provider is None:
        if any(value is not None for value in synthesis_identity):
            raise ValueError("synthesis identity requires a synthesis provider")
    elif any(not isinstance(value, str) or not value.strip() for value in synthesis_identity):
        raise ValueError("synthesis provider, model and revision are required")
    jobs = SQLiteJobs(Path(db_path))
    wake = asyncio.Event()
    synthesis_lock = asyncio.Lock()

    async def run_once() -> bool:
        job = jobs.claim_next()
        if job is None:
            return False
        if (job.provider, job.model, job.revision, job.max_chars) != (
                provider_name, model, revision, max_chars):
            jobs.finish(job.id, "INTERRUPTED", "CONFIGURATION_CHANGED")
            return True
        try:
            checkpoint = SQLiteSectionCheckpoint(
                jobs.path, run_id=job.id, transcript=job.transcript,
                provider=job.provider, model=job.model, revision=job.revision,
                max_chars=job.max_chars,
            )
            result = await analyze_with_checkpoint(checkpoint, analysis_provider)
            if result.complete:
                jobs.finish(job.id, "COMPLETED")
            else:
                failure = result.failure
                assert failure is not None
                if failure.remote_outcome_unknown:
                    jobs.finish(job.id, "INTERRUPTED", "REMOTE_OUTCOME_UNKNOWN")
                elif failure.code == "RATE_LIMITED":
                    jobs.finish(job.id, "WAITING_RATE_LIMIT", "RATE_LIMITED")
                else:
                    jobs.finish(job.id, "FAILED", safe_code(failure.code))
        except asyncio.CancelledError:
            jobs.finish(job.id, "INTERRUPTED", "REMOTE_OUTCOME_UNKNOWN")
            raise
        except (CheckpointMismatch, ChunkPlanningError, ValueError):
            jobs.finish(job.id, "FAILED", "INVALID_JOB_CONFIGURATION")
        except Exception:
            jobs.finish(job.id, "FAILED", "INTERNAL_ERROR")
        return True

    async def worker() -> None:
        while True:
            if await run_once():
                await asyncio.sleep(0)
                continue
            wake.clear()
            try:
                await asyncio.wait_for(wake.wait(), timeout=0.25)
            except TimeoutError:
                pass

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        lock_file = None
        try:
            jobs.path.parent.mkdir(parents=True, exist_ok=True)
            lock_file = (jobs.path.parent / (jobs.path.name + ".worker.lock")).open("a+b")
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RuntimeError("another SignalTranscript worker is active") from exc
            jobs.initialize()
            jobs.recover_interrupted()
            task = asyncio.create_task(worker())
            try:
                yield
            finally:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        finally:
            if lock_file is not None:
                lock_file.close()
            if on_provider_shutdown is not None:
                await on_provider_shutdown()
            if on_synthesis_provider_shutdown is not None:
                await on_synthesis_provider_shutdown()

    app = FastAPI(title="SignalTranscript local analysis", lifespan=lifespan)

    @app.post("/api/jobs", status_code=202)
    async def submit(payload: ImportInput):
        try:
            transcript_payload = payload.model_dump(exclude={"evidence", "caption_verification"})
            if payload.caption_verification is not None and payload.evidence is None:
                raise CaptionEvidenceError("CAPTION_VERIFICATION_REQUIRES_EVIDENCE")
            if payload.caption_verification is not None:
                evidence = verify_submitted_caption(
                    payload.evidence, transcript_payload,
                    caption_text=payload.caption_verification.text,
                    caption_format=payload.caption_verification.format,
                )
            else:
                evidence = (parse_manifest(payload.evidence, transcript_payload)
                            if payload.evidence is not None else None)
            transcript = Transcript(
                video_id=payload.video_id, source=payload.source,
                language=payload.language,
                segments=tuple(Segment(**segment.model_dump()) for segment in payload.segments),
            )
            job = jobs.enqueue(transcript, provider=provider_name, model=model,
                               revision=revision, max_chars=max_chars, evidence=evidence)
        except (CaptionEvidenceError, ValueError, ChunkPlanningError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)[:100]) from None
        wake.set()
        return view(jobs, job)

    @app.get("/api/jobs/{job_id}")
    async def get_job(job_id: str):
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="JOB_NOT_FOUND")
        return view(jobs, job)

    @app.post("/api/jobs/{job_id}/resume", status_code=202)
    async def resume(job_id: str):
        try:
            job = jobs.resume(job_id, provider=provider_name, model=model,
                              revision=revision, max_chars=max_chars)
        except KeyError:
            raise HTTPException(status_code=404, detail="JOB_NOT_FOUND") from None
        except JobConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from None
        wake.set()
        return view(jobs, job)

    @app.post("/api/jobs/{job_id}/cancel", status_code=200)
    async def cancel(job_id: str):
        try:
            job = jobs.cancel(job_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="JOB_NOT_FOUND") from None
        except JobConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from None
        return view(jobs, job)

    @app.get("/api/jobs/{job_id}/sections")
    async def sections(job_id: str):
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="JOB_NOT_FOUND")
        if jobs.completed_sections(job.id) == 0 and job.state != "COMPLETED":
            return {"job_id": job.id, "complete": False, "result_kind": "SECTIONS_ONLY",
                    "planned_sections": job.section_count, "sections": [],
                    "provenance": provenance_view(job)}
        try:
            checkpoint = SQLiteSectionCheckpoint(
                jobs.path, run_id=job.id, transcript=job.transcript,
                provider=job.provider, model=job.model, revision=job.revision,
                max_chars=job.max_chars,
            )
            completed = checkpoint.open_and_load()
            if job.state == "COMPLETED" and len(completed) != job.section_count:
                raise CheckpointMismatch("INCOMPLETE_CHECKPOINT")
        except (CheckpointMismatch, ValueError, ChunkPlanningError):
            raise HTTPException(status_code=409, detail="INVALID_CHECKPOINT") from None
        return {"job_id": job.id, "complete": job.state == "COMPLETED",
                "result_kind": "SECTIONS_ONLY", "planned_sections": job.section_count,
                "sections": [asdict(section) for section in completed],
                "provenance": provenance_view(job)}


    def synthesis_checkpoint_for(job: Job) -> SQLiteGlobalSynthesisCheckpoint:
        if synthesis_provider_name is None or synthesis_model is None or synthesis_revision is None:
            raise HTTPException(status_code=409, detail="SYNTHESIS_PROVIDER_NOT_CONFIGURED")
        if job.state != "COMPLETED":
            raise HTTPException(status_code=409, detail="SECTIONS_NOT_COMPLETE")
        try:
            section_checkpoint = SQLiteSectionCheckpoint(
                jobs.path, run_id=job.id, transcript=job.transcript,
                provider=job.provider, model=job.model, revision=job.revision,
                max_chars=job.max_chars,
            )
            completed = section_checkpoint.open_and_load()
            if len(completed) != job.section_count:
                raise CheckpointMismatch("INCOMPLETE_CHECKPOINT")
            sectioned = SectionedAnalysis(
                job.transcript.video_id, job.section_count, completed,
            )
            return SQLiteGlobalSynthesisCheckpoint(
                jobs.path, run_id=job.id, transcript=job.transcript,
                sectioned=sectioned, provider=synthesis_provider_name,
                model=synthesis_model, revision=synthesis_revision,
            )
        except (CheckpointMismatch, SynthesisCheckpointMismatch,
                SynthesisValidationError, ChunkPlanningError, ValueError):
            raise HTTPException(status_code=409, detail="INVALID_SYNTHESIS_CHECKPOINT") from None

    def synthesis_view(job: Job, result) -> dict[str, object]:
        return {
            "job_id": job.id,
            "result_kind": "GLOBAL_SYNTHESIS",
            "analysis": asdict(result.analysis),
            "coverage": asdict(result.coverage),
            "provenance": provenance_view(job),
        }

    @app.get("/api/jobs/{job_id}/synthesis")
    async def get_synthesis(job_id: str):
        """Read only a previously persisted synthesis; never invokes a provider."""
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="JOB_NOT_FOUND")
        checkpoint = synthesis_checkpoint_for(job)
        try:
            result = checkpoint.load_existing()
        except SynthesisCheckpointMismatch:
            raise HTTPException(status_code=409, detail="INVALID_SYNTHESIS_CHECKPOINT") from None
        except Exception:
            raise HTTPException(status_code=500, detail="SYNTHESIS_INTERNAL_ERROR") from None
        if result is None:
            raise HTTPException(status_code=404, detail="SYNTHESIS_NOT_FOUND")
        return synthesis_view(job, result)

    @app.post("/api/jobs/{job_id}/synthesis")
    async def synthesize(job_id: str):
        """Explicit global synthesis; never triggered automatically by section completion."""
        if synthesis_provider is None:
            raise HTTPException(status_code=409, detail="SYNTHESIS_PROVIDER_NOT_CONFIGURED")
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="JOB_NOT_FOUND")
        checkpoint = synthesis_checkpoint_for(job)
        async with synthesis_lock:
            try:
                result = await synthesize_with_checkpoint(checkpoint, synthesis_provider)
            except ProviderFailure as failure:
                if failure.remote_outcome_unknown:
                    raise HTTPException(
                        status_code=409, detail="SYNTHESIS_REMOTE_OUTCOME_UNKNOWN",
                    ) from None
                if failure.code == "RATE_LIMITED":
                    raise HTTPException(status_code=429, detail="SYNTHESIS_RATE_LIMITED") from None
                raise HTTPException(status_code=502, detail="SYNTHESIS_PROVIDER_FAILURE") from None
            except (CheckpointMismatch, SynthesisCheckpointMismatch,
                    SynthesisValidationError, ChunkPlanningError, ValueError):
                raise HTTPException(status_code=409, detail="INVALID_SYNTHESIS_CHECKPOINT") from None
            except Exception:
                raise HTTPException(status_code=500, detail="SYNTHESIS_INTERNAL_ERROR") from None
        return synthesis_view(job, result)

    return app
