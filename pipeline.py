"""Pipeline orchestrator — manages job state and stage execution."""
import asyncio
import json
import uuid
import time
from typing import Callable

from stages import scraper, analyzer, profiler, voice, library, inspiration, generator

JOBS: dict[str, dict] = {}


def create_job(handle: str, inspiration_urls: list[str], inspiration_note: str) -> str:
    """Create a new job, return job_id."""
    job_id = str(uuid.uuid4())[:8]
    JOBS[job_id] = {
        "job_id": job_id,
        "handle": handle,
        "inspiration_urls": inspiration_urls,
        "inspiration_note": inspiration_note,
        "status": "pending",
        "created_at": time.time(),
        "videos": [],
        "analyzed_videos": [],
        "profile": None,
        "voice": None,
        "library_intel": None,
        "inspiration_digest": None,
        "briefs": None,
        "events": [],  # buffered SSE events for late subscribers
        "error": None,
        # intent inputs (set when user submits screen 2)
        "intent": "",
        "strategy": None,
        "library_selections": {"brief_1": True, "brief_2": True, "brief_3": True},
        "skip_library": False,
        "regen_brief_num": None,
    }
    return job_id


def get_job(job_id: str) -> dict | None:
    return JOBS.get(job_id)


def format_sse(event_type: str, data: dict) -> str:
    """Return a formatted SSE event string."""
    payload = json.dumps(data)
    return f"event: {event_type}\ndata: {payload}\n\n"


async def run_preflight(job_id: str, emit: Callable) -> None:
    """Run stages A-D (scraper → analyzer → profiler → voice → library → inspiration)."""
    job = JOBS[job_id]
    job["status"] = "running_preflight"
    try:
        emit("progress", {"stage": "scraper", "message": "Fetching creator videos..."})
        await scraper.run(job, emit)

        emit("progress", {"stage": "analyzer", "message": "Analyzing video content..."})
        await analyzer.run(job, emit)

        emit("progress", {"stage": "profiler", "message": "Building creator profile..."})
        await profiler.run(job, emit)

        emit("progress", {"stage": "voice", "message": "Fingerprinting creator voice..."})
        await voice.run(job, emit)

        emit("progress", {"stage": "library", "message": "Fetching library intelligence..."})
        await library.run(job, emit)

        emit("progress", {"stage": "inspiration", "message": "Processing inspiration URLs..."})
        await inspiration.run(job, emit)

        job["status"] = "awaiting_intent"
        emit("preflight_complete", {
            "archetype": job["profile"]["archetype"] if job["profile"] else "unknown",
            "archetype_confidence": job["profile"]["archetype_confidence"] if job["profile"] else 0,
            "videos_analyzed": len(job["analyzed_videos"]),
            "library_available": (
                job["library_intel"] is not None
                and job["library_intel"].get("available", False)
            ),
        })
    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)
        emit("error", {"message": str(e), "stage": "preflight"})


async def run_generation(job_id: str, emit: Callable) -> None:
    """Run stage E+F (generation + scoring). Called after user submits intent."""
    job = JOBS[job_id]
    job["status"] = "running_generation"
    try:
        emit("progress", {"stage": "generator", "message": "Generating content briefs..."})
        await generator.run(job, emit)

        job["status"] = "complete"
        emit("complete", {"briefs": job["briefs"]})
    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)
        emit("error", {"message": str(e), "stage": "generation"})
