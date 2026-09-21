"""Opt-in, loopback-only entrypoint for the single-process analysis backend.

This is the composition root. Groq is registered here, not imported by the
backend or provider-neutral contracts. Never starts a paid provider by default.
"""

import argparse
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path

from fastapi import FastAPI

from signaltranscript.ai.adapters.groq_analysis import (
    ANALYSIS_SCHEMA, MAX_COMPLETION_TOKENS, MAX_INPUT_CHARS, MODEL,
    SYSTEM_INSTRUCTIONS, GroqAnalysisAdapter,
)
from signaltranscript.ai.ports import AnalysisProvider
from signaltranscript.backend.api import create_app


@dataclass(frozen=True, slots=True)
class AnalysisRegistration:
    name: str
    model: str
    revision: str
    max_chars: int
    create: Callable[[], AnalysisProvider]


def groq_revision() -> str:
    """Invalidate old checkpoints when the model, prompt or response contract changes."""
    contract = {
        "model": MODEL,
        "system_instructions": SYSTEM_INSTRUCTIONS,
        "analysis_schema": ANALYSIS_SCHEMA,
        "max_completion_tokens": MAX_COMPLETION_TOKENS,
        "response_mode": "json_schema_strict_v1",
    }
    serialized = json.dumps(contract, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return "groq-analysis-" + sha256(serialized.encode("utf-8")).hexdigest()


def available_providers() -> dict[str, AnalysisRegistration]:
    """Additional providers register a constructor and their own model/revision."""
    return {"groq": AnalysisRegistration(
        "groq", MODEL, groq_revision(), MAX_INPUT_CHARS,
        GroqAnalysisAdapter.from_environment,
    )}


def build_app(*, provider: str, db_path: Path,
              registry: Mapping[str, AnalysisRegistration] | None = None) -> FastAPI:
    """Reject unknown/unconfigured providers; never silently select an alternative."""
    registrations = available_providers() if registry is None else registry
    registration = registrations.get(provider)
    if registration is None:
        raise ValueError("ANALYSIS_PROVIDER_NOT_REGISTERED")
    if (registration.name != provider or not registration.model.strip()
            or not registration.revision.strip() or type(registration.max_chars) is not int
            or registration.max_chars <= 0):
        raise ValueError("INVALID_ANALYSIS_REGISTRATION")
    instance = registration.create()
    close = getattr(instance, "aclose", None)
    app = create_app(
        Path(db_path), analysis_provider=instance, provider_name=registration.name,
        model=registration.model, revision=registration.revision,
        max_chars=registration.max_chars,
        on_provider_shutdown=close if callable(close) else None,
    )

    @app.get("/api/config")
    async def public_local_config():
        """Non-secret identity for explicit consent BEFORE posting transcripts."""
        return {"analysis_provider": registration.name, "model": registration.model,
                "result_kind": "SECTIONS_ONLY"}

    return app


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SignalTranscript local analysis server")
    parser.add_argument("--analysis-provider", required=True, choices=tuple(available_providers()),
                        help="Explicitly select the analysis provider; no automatic fallback")
    default_dir = Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share")) / "signaltranscript"
    parser.add_argument("--data-dir", type=Path, default=default_dir)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")

    if not args.data_dir.is_absolute() or args.data_dir.is_symlink():
        parser.error("--data-dir must be an absolute, non-symlink directory")
    if args.data_dir.exists():
        if not args.data_dir.is_dir() or args.data_dir.stat().st_mode & 0o077:
            parser.error("data directory must be private (permissions 0700)")
    database = args.data_dir / "signaltranscript.db"
    if database.is_symlink() or (database.exists() and database.stat().st_mode & 0o077):
        parser.error("database file must be private (permissions 0600)")

    # Files created in this process, including SQLite's WAL/SHM files, are private.
    old_umask = os.umask(0o077)
    try:
        try:
            app = build_app(provider=args.analysis_provider, db_path=database)
        except (RuntimeError, ValueError, ImportError):
            # Never include SDK responses, environment values or secrets in startup errors.
            parser.error("analysis provider unavailable or improperly configured")
        import uvicorn
        uvicorn.run(app, host="127.0.0.1", port=args.port, workers=1, reload=False,
                    proxy_headers=False, access_log=False)
        return 0
    finally:
        os.umask(old_umask)


if __name__ == "__main__":
    raise SystemExit(main())
