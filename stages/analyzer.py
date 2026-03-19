"""Stage B: Analyzer — Gemini 2.5 Flash visual beat analysis + GPT-5.4 pattern extraction.
Videos are analyzed ONE AT A TIME to avoid Gemini threading issues / memory spikes.
"""
import os
import asyncio
import json
import logging
import tempfile
import time
from typing import Callable

import httpx
import google.generativeai as genai
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

genai.configure(api_key=GOOGLE_API_KEY)

# Module-level model — not thread-safe to create per-call
GEMINI_MODEL = genai.GenerativeModel(
    model_name="gemini-2.5-flash",
    safety_settings={
        cat: genai.types.HarmBlockThreshold.BLOCK_NONE
        for cat in [
            genai.types.HarmCategory.HARM_CATEGORY_HARASSMENT,
            genai.types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
            genai.types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
            genai.types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
        ]
    },
)

openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# Max 2 Gemini uploads at a time — parallel but bounded to avoid RAM spikes / segfaults
GEMINI_SEMAPHORE = asyncio.Semaphore(2)

B1_PROMPT = """Analyze this TikTok video beat by beat. Return ONLY valid JSON matching this exact schema:
{
  "duration_seconds": <int>,
  "beat_count": <int>,
  "beats": [
    {"time": "0-3s", "beat_num": 1, "action": "<exact visual description>", "text_overlay": "<exact on-screen text or null>", "audio": "<verbatim spoken words or null>", "product_integration": null}
  ],
  "hook_text": "<first 3 seconds verbatim audio>",
  "transcript": "<full verbatim transcript>"
}
For product_integration: use "first_appearance" when product is first shown, "on_screen" for subsequent appearances, null otherwise.
Capture every beat. Be extremely precise about audio (verbatim words). Return only JSON, no markdown."""

B2_SYSTEM = """You are a TikTok content analyst for supplement brands.
Given a beat-by-beat video analysis, extract content patterns.
Return ONLY valid JSON. No markdown, no explanation."""

B2_USER = """Extract patterns from this beat analysis:

{b1_json}

Return JSON with exactly these fields:
{{
  "hook_type": "<relatable_callout|bold_claim|before_after|negative_framing|controversial_take|personal_story|social_proof_callout|fomo_urgency|shock_value|curiosity_gap|authority_intro|question>",
  "narrative_arc": "<problem_solution|testimonial|before_after|product_showcase|comparison|enemy_hero|listicle|social_proof_cascade|tutorial|debunk>",
  "pain_point": "<sleep|brain_fog|stress_cortisol|low_energy|muscle_recovery|pms_hormones|general_wellness|other>",
  "product_integration_method": "<early_hook|mid_reveal|end_reveal|throughout|never>",
  "cta_type": "<link_in_bio|comment_for_link|direct_shop|discount_code|none>",
  "authority_signals": ["<credentials or trust signals used>"],
  "pain_point_clarity": <1-5>,
  "transformation_proof": <true|false>,
  "social_proof_present": <true|false>,
  "coa_lab_present": <true|false>,
  "archetype_signals": ["<pharmacist|wellness_influencer|fitness_coach|ugc_creator|etc>"]
}}"""


def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if "```" in text:
            text = text[: text.rfind("```")]
    return json.loads(text.strip())


def _gemini_analyze_sync(video_bytes: bytes, apify_transcript: str) -> dict:
    """Sync: upload to Gemini, wait for ACTIVE, generate beat analysis. Called in executor."""
    tmp_path = None
    gemini_file = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            tmp.write(video_bytes)
            tmp_path = tmp.name

        gemini_file = genai.upload_file(tmp_path, mime_type="video/mp4")

        # Poll until ACTIVE (max 90s)
        for _ in range(90):
            if gemini_file.state.name == "ACTIVE":
                break
            if gemini_file.state.name == "FAILED":
                raise RuntimeError("Gemini file processing FAILED")
            time.sleep(1)
            gemini_file = genai.get_file(gemini_file.name)
        else:
            raise RuntimeError("Gemini file never became ACTIVE after 90s")

        # Add transcript context to prompt if available
        prompt = B1_PROMPT
        if apify_transcript:
            prompt = f"Apify transcript for reference:\n{apify_transcript[:1500]}\n\n" + B1_PROMPT

        response = GEMINI_MODEL.generate_content([gemini_file, prompt])
        return _parse_json(response.text)

    finally:
        # Always clean up
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        if gemini_file:
            try:
                genai.delete_file(gemini_file.name)
            except Exception:
                pass


async def analyze_video(video: dict, idx: int, total: int, emit: Callable) -> dict:
    """Download video, B1 with Gemini Flash, B2 with GPT-5.4."""
    video_id = video.get("video_id", f"video_{idx}")
    download_url = video.get("download_url") or video.get("url") or ""

    if not download_url:
        logger.warning("Video %s has no download URL", video_id)
        return {**video, "b1": None, "b2": None, "error": "no_url"}

    # Download
    emit("progress", {"stage": "B", "message": f"Video {idx}/{total}: downloading..."})
    try:
        async with httpx.AsyncClient(timeout=120, follow_redirects=True) as http:
            resp = await http.get(download_url)
            resp.raise_for_status()
            video_bytes = resp.content
    except Exception as e:
        logger.warning("Download failed for %s: %s", video_id, e)
        return {**video, "b1": None, "b2": None, "error": f"download_failed: {e}"}

    size_kb = len(video_bytes) // 1024
    emit("progress", {"stage": "B", "message": f"Video {idx}/{total}: {size_kb}KB downloaded. Uploading to Gemini..."})

    # B1 — Gemini (max 2 concurrent via semaphore)
    apify_transcript = video.get("transcript") or ""
    async with GEMINI_SEMAPHORE:
        try:
            loop = asyncio.get_event_loop()
            b1 = await asyncio.wait_for(
                loop.run_in_executor(None, _gemini_analyze_sync, video_bytes, apify_transcript),
                timeout=180,
            )
            del video_bytes  # free memory immediately
        except Exception as e:
            logger.warning("B1 Gemini failed for %s: %s", video_id, e)
            del video_bytes
            return {**video, "b1": None, "b2": None, "error": f"b1_failed: {e}"}

    emit("progress", {"stage": "B", "message": f"Video {idx}/{total}: Gemini done. Extracting patterns..."})

    # B2 — GPT-5.4
    try:
        b2_resp = await openai_client.chat.completions.create(
            model="gpt-5.4",
            messages=[
                {"role": "system", "content": B2_SYSTEM},
                {"role": "user", "content": B2_USER.format(b1_json=json.dumps(b1, indent=2)[:4000])},
            ],
            temperature=0.2,
            timeout=60,
        )
        b2 = _parse_json(b2_resp.choices[0].message.content)
    except Exception as e:
        logger.warning("B2 GPT failed for %s: %s", video_id, e)
        return {**video, "b1": b1, "b2": None, "error": f"b2_failed: {e}"}

    emit("progress", {
        "stage": "B",
        "message": f"Video {idx}/{total} done — {b2.get('hook_type', '?')} / {b2.get('pain_point', '?')}",
    })
    return {**video, "b1": b1, "b2": b2, "error": None}


async def run(job: dict, emit: Callable) -> None:
    """Stage B: analyze videos in parallel batches of 2 (semaphore-bounded)."""
    videos = job.get("videos", [])
    if not videos:
        emit("progress", {"stage": "B", "message": "No videos to analyze.", "done": True})
        job["analyzed_videos"] = []
        return

    total = len(videos)
    emit("progress", {"stage": "B", "message": f"Starting Gemini analysis of {total} videos (2 at a time)..."})

    tasks = [analyze_video(video, i + 1, total, emit) for i, video in enumerate(videos)]
    results = await asyncio.gather(*tasks)

    job["analyzed_videos"] = results
    successful = sum(1 for r in results if not r.get("error"))
    emit("progress", {
        "stage": "B",
        "message": f"Analysis complete — {successful}/{total} videos analyzed",
        "done": True,
    })
    logger.info("Stage B complete: %d/%d videos", successful, total)
