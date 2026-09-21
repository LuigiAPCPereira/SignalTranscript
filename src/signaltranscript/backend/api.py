"""Local HTTP shell for imported-transcript analysis, not a public server.

The app factory requires a chosen provider. There is no default Groq key,
implicit provider switch, network acquisition, or hidden retry.
"""

import asyncio
from contextlib import asynccontextmanager
from dataclasses import asdict
import fcntl
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from signaltranscript.ai.long_form import ChunkPlanningError
from signaltranscript.ai.ports import AnalysisProvider, Segment, Transcript
from signaltranscript.ai.section_checkpoint import (
    CheckpointMismatch, SQLiteSectionCheckpoint, analyze_with_checkpoint,
)
from signaltranscript.backend.jobs import Job, JobConflict, SQLiteJobs, safe_code


class SegmentInput(BaseModel):
    id: str = Field(min_length=1, max_length=256)
    text: str = Field(min_length=1, max_length=12_000)
    start_ms: int | None = None
    end_ms: int | None = None


class ImportInput(BaseModel):
    video_id: str = Field(min_length=1, max_length=256)
    source: str = Field(min_length=1, max_length=256)
    language: str | None = Field(default=None, max_length=64)
    segments: list[SegmentInput] = Field(min_length=1, max_length=4_096)


def view(jobs: SQLiteJobs, job: Job) -> dict[str, object]:
    return {"id": job.id, "video_id": job.transcript.video_id, "state": job.state,
            "provider": job.provider, "model": job.model, "attempts": job.attempts,
            "planned_sections": job.section_count,
            "completed_sections": jobs.completed_sections(job.id), "error_code": job.error_code,
            "result_kind": "SECTIONS_ONLY" if job.state == "COMPLETED" else None}


def create_app(db_path: Path, *, analysis_provider: AnalysisProvider, provider_name: str,
               model: str, revision: str, max_chars: int = 12_000) -> FastAPI:
    """One Linux process, one injected provider, one sequential worker."""
    if any(not isinstance(v, str) or not v.strip() for v in (provider_name, model, revision)):
        raise ValueError("provider, model and revision are required")
    if type(max_chars) is not int or max_chars <= 0:
        raise ValueError("max_chars must be a positive integer")
    jobs = SQLiteJobs(Path(db_path))
    wake = asyncio.Event()

    async def run_once() -> bool:
        job = jobs.claim_next()
        if job is None:
            return False
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
            # Never return raw provider responses or filesystem errors to clients.
            jobs.finish(job.id, "FAILED", "INTERNAL_ERROR")
        return True

    async def worker() -> None:
        while True:
            if await run_once():
                await asyncio.sleep(0)  # allow HTTP requests between jobs
                continue
            wake.clear()
            # There may have been an enqueue just before clear(): periodic wake
            # prevents lost notifications; tasks remain durable in SQLite.
            try:
                await asyncio.wait_for(wake.wait(), timeout=0.25)
            except TimeoutError:
                pass

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        jobs.path.parent.mkdir(parents=True, exist_ok=True)
        lock_file = (jobs.path.parent / (jobs.path.name + ".worker.lock")).open("a+b")
        try:
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
            lock_file.close()

    app = FastAPI(title="SignalTranscript local analysis", lifespan=lifespan)

    @app.post("/api/jobs", status_code=202)
    async def submit(payload: ImportInput):
        try:
            transcript = Transcript(
                video_id=payload.video_id, source=payload.source,
                language=payload.language,
                segments=tuple(Segment(**segment.model_dump()) for segment in payload.segments),
            )
            job = jobs.enqueue(transcript, provider=provider_name, model=model,
                               revision=revision, max_chars=max_chars)
        except (ValueError, ChunkPlanningError) as exc:
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

    @app.get("/api/jobs/{job_id}/sections")
    async def sections(job_id: str):
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="JOB_NOT_FOUND")
        if jobs.completed_sections(job.id) == 0 and job.state != "COMPLETED":
            return {"job_id": job.id, "complete": False, "result_kind": "SECTIONS_ONLY",
                    "planned_sections": job.section_count, "sections": []}
        try:
            checkpoint = SQLiteSectionCheckpoint(
                jobs.path, run_id=job.id, transcript=job.transcript,
                provider=job.provider, model=job.model, revision=job.revision,
                max_chars=job.max_chars,
            )
            completed = checkpoint.open_and_load()
        except (CheckpointMismatch, ValueError, ChunkPlanningError):
            raise HTTPException(status_code=409, detail="INVALID_CHECKPOINT") from None
        return {"job_id": job.id, "complete": job.state == "COMPLETED",
                "result_kind": "SECTIONS_ONLY", "planned_sections": job.section_count,
                "sections": [asdict(section) for section in completed]}

    return app
