from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional
import asyncio
import json
import os

from dotenv import load_dotenv
load_dotenv()  # MUST be before pipeline import — stages read os.getenv at module level

from pipeline import create_job, get_job, run_preflight, run_generation, format_sse, JOBS

app = FastAPI(title="Magcontentinator")
templates = Jinja2Templates(directory="templates")


# ── Request schemas ──

class StartRequest(BaseModel):
    handle: str
    inspiration_urls: list[str] = []
    inspiration_note: str = ""


class GenerateRequest(BaseModel):
    intent: str = ""
    strategy: Optional[str] = None
    library_selections: dict = {"brief_1": True, "brief_2": True, "brief_3": True}
    skip_library: bool = False


class RegenRequest(BaseModel):
    feedback: str = ""


# ── Helper ──

def make_emit(job_id: str):
    """Return a synchronous emit callable bound to a job.
    Uses put_nowait so stages don't need to await it."""
    def emit(event_type: str, data: dict):
        event_str = format_sse(event_type, data)
        job = JOBS.get(job_id)
        if not job:
            return
        job["events"].append(event_str)
        for q in list(job.get("_queues", {}).values()):
            try:
                q.put_nowait(event_str)
            except Exception:
                pass
    return emit


# ── Routes ──

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/start")
async def start(req: StartRequest, background_tasks: BackgroundTasks):
    handle = req.handle.lstrip("@").strip()
    job_id = create_job(handle, req.inspiration_urls, req.inspiration_note)
    emit = make_emit(job_id)
    background_tasks.add_task(run_preflight, job_id, emit)
    return {"job_id": job_id}


@app.get("/api/stream/{job_id}")
async def stream(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator():
        # Replay buffered events for late subscribers
        for event in list(job.get("events", [])):
            yield event

        # If already terminal, nothing more to stream
        if job["status"] in ("complete", "error"):
            return

        # Set up a queue for new events emitted after connection.
        # Use the queue object itself as its key to avoid race conditions
        # when a client reconnects before the old generator's finally runs.
        queue: asyncio.Queue = asyncio.Queue()
        queues = job.setdefault("_queues", {})
        queue_key = id(queue)
        queues[queue_key] = queue

        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30)
                    yield event
                    # Stop streaming once a terminal event is sent
                    if 'event: complete\n' in event or 'event: error\n' in event:
                        break
                except asyncio.TimeoutError:
                    # Send a keepalive comment to prevent connection timeout
                    yield ": keepalive\n\n"
        finally:
            job.get("_queues", {}).pop(queue_key, None)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/generate/{job_id}")
async def generate(job_id: str, req: GenerateRequest, background_tasks: BackgroundTasks):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] not in ("awaiting_intent", "complete", "error"):
        raise HTTPException(
            status_code=409,
            detail=f"Job is not ready for generation (status: {job['status']})",
        )

    job["intent"] = req.intent
    job["strategy"] = req.strategy
    job["library_selections"] = req.library_selections
    job["skip_library"] = req.skip_library
    job["regen_brief_num"] = None

    emit = make_emit(job_id)
    background_tasks.add_task(run_generation, job_id, emit)
    return {"status": "generating"}


@app.post("/api/skip-to-transcripts/{job_id}")
async def skip_to_transcripts(job_id: str):
    """User hit the 'use transcripts' skip button — flag the job to use transcript mode."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job["use_transcripts"] = True
    return {"status": "ok"}


@app.post("/api/regen/{job_id}/{brief_num}")
async def regen(
    job_id: str,
    brief_num: int,
    req: RegenRequest,
    background_tasks: BackgroundTasks,
):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] not in ("complete", "error"):
        raise HTTPException(
            status_code=409,
            detail=f"Job briefs not yet available (status: {job['status']})",
        )

    job["regen_brief_num"] = brief_num
    job["regen_feedback"] = req.feedback
    job["status"] = "running_generation"

    emit = make_emit(job_id)
    background_tasks.add_task(run_generation, job_id, emit)
    return {"status": "regenerating"}


@app.get("/api/job/{job_id}")
async def get_job_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "job_id": job["job_id"],
        "handle": job["handle"],
        "status": job["status"],
        "profile": job.get("profile"),
        "voice": job.get("voice"),
        "library_intel": job.get("library_intel"),
        "briefs": job.get("briefs"),
        "error": job.get("error"),
        "videos_analyzed": len(job.get("analyzed_videos", [])),
    }
