"""Stage B: Analyzer — Pass B1 (Gemini 2.5 Flash structural) + Pass B2 (GPT-5.4 patterns)."""
import os
import asyncio
import httpx
import json
import tempfile
import time
import logging
from typing import Callable

import google.generativeai as genai
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

genai.configure(api_key=GOOGLE_API_KEY)
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# Limit concurrent video analyses to avoid hammering APIs / memory
SEMAPHORE = asyncio.Semaphore(3)

B1_PROMPT = """Analyze this TikTok video beat by beat. Return ONLY valid JSON matching this exact schema:
{
  "duration_seconds": <int>,
  "beat_count": <int>,
  "beats": [
    {"time": "0-3s", "beat_num": 1, "action": "<exact visual description>", "text_overlay": "<exact on-screen text or null>", "audio": "<verbatim spoken words or null>", "product_integration": null | "first_appearance" | "on_screen"}
  ],
  "hook_text": "<first 3 seconds verbatim audio>",
  "transcript": "<full verbatim transcript>"
}
Capture every beat. Be extremely precise about audio (verbatim words). Return only JSON, no markdown."""

B2_SYSTEM = """You are a TikTok content analyst specializing in supplement/wellness content.
Given a structural beat analysis JSON, extract content patterns.
Return ONLY valid JSON. No markdown, no explanation."""

B2_USER_TEMPLATE = """Analyze this beat-by-beat video data and extract patterns:

{b1_json}

Return JSON with exactly these fields:
{{
  "hook_type": "<one of: relatable_callout|bold_claim|before_after|negative_framing|controversial_take|personal_story|social_proof_callout|fomo_urgency|shock_value|curiosity_gap|authority_intro|question>",
  "narrative_arc": "<one of: problem_solution|testimonial|before_after|product_showcase|comparison|enemy_hero|listicle|social_proof_cascade|tutorial|debunk>",
  "pain_point": "<primary pain point addressed: sleep|brain_fog|stress_cortisol|low_energy|muscle_recovery|pms_hormones|general_wellness|other>",
  "product_integration_method": "<how product appears: early_hook|mid_reveal|end_reveal|throughout|never>",
  "cta_type": "<link_in_bio|comment_for_link|direct_shop|discount_code|none>",
  "authority_signals": ["<list any credentials, expertise, trust signals used>"],
  "pain_point_clarity": <1-5, how clearly is pain point established>,
  "transformation_proof": <true|false, does it show before/after or result proof>,
  "social_proof_present": <true|false>,
  "coa_lab_present": <true|false, any lab results or COA shown>,
  "estimated_duration": "<e.g. 45-60s>",
  "archetype_signals": ["<creator type signals: pharmacist|wellness_influencer|fitness_coach|ugc_creator|etc>"]
}}"""


def _parse_json_response(text: str) -> dict:
    """Strip markdown fences if present and parse JSON."""
    text = text.strip()
    if text.startswith("```"):
        # Remove opening fence (e.g. ```json)
        text = text.split("\n", 1)[-1]
        # Remove closing fence
        if text.endswith("```"):
            text = text[: text.rfind("```")]
    return json.loads(text.strip())


async def _upload_to_gemini(video_bytes: bytes, mime_type: str = "video/mp4") -> genai.types.File:
    """Upload video bytes to the Gemini File API and wait until processing completes."""
    loop = asyncio.get_event_loop()

    # Write bytes to a temp file — genai.upload_file expects a path or file-like
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp.write(video_bytes)
        tmp_path = tmp.name

    # Upload runs synchronously inside an executor to avoid blocking the event loop
    def _upload():
        return genai.upload_file(tmp_path, mime_type=mime_type)

    uploaded = await loop.run_in_executor(None, _upload)

    # Poll until the file is ACTIVE (Gemini processes asynchronously)
    def _wait_active(f):
        for _ in range(60):  # up to ~60s
            if f.state.name == "ACTIVE":
                return f
            if f.state.name == "FAILED":
                raise RuntimeError(f"Gemini file processing failed: {f.name}")
            time.sleep(1)
            f = genai.get_file(f.name)
        raise RuntimeError("Gemini file never became ACTIVE after 60s.")

    active_file = await loop.run_in_executor(None, _wait_active, uploaded)

    # Clean up temp file
    try:
        os.unlink(tmp_path)
    except OSError:
        pass

    return active_file


async def _b1_gemini(video_bytes: bytes) -> dict:
    """Pass B1: structural beat-by-beat analysis via Gemini 2.5 Flash."""
    loop = asyncio.get_event_loop()

    gemini_file = await _upload_to_gemini(video_bytes)

    model = genai.GenerativeModel(
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

    def _generate():
        response = model.generate_content([gemini_file, B1_PROMPT])
        return response.text

    raw_text = await loop.run_in_executor(None, _generate)
    return _parse_json_response(raw_text)


async def _b2_gpt(b1_data: dict) -> dict:
    """Pass B2: pattern extraction via GPT-5.4."""
    b1_json = json.dumps(b1_data, indent=2)
    user_prompt = B2_USER_TEMPLATE.format(b1_json=b1_json)

    response = await openai_client.chat.completions.create(
        model="gpt-5.4",
        messages=[
            {"role": "system", "content": B2_SYSTEM},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
    )
    return _parse_json_response(response.choices[0].message.content)


async def analyze_video(video: dict, idx: int, total: int, emit: Callable) -> dict:
    """Download a video, run B1 (Gemini Flash) then B2 (GPT-5.4), return combined result."""
    async with SEMAPHORE:
        video_id = video.get("video_id", f"video_{idx}")
        emit(
            "progress",
            {
                "stage": "B",
                "message": f"Analyzing video {idx}/{total} ({video_id})...",
                "video_index": idx,
                "total": total,
            },
        )

        download_url = video.get("download_url") or video.get("url", "")
        if not download_url:
            logger.warning("Video %s has no download URL — skipping.", video_id)
            return {**video, "b1": None, "b2": None, "error": "no_download_url"}

        # Download video bytes
        try:
            async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
                dl_resp = await client.get(download_url)
                dl_resp.raise_for_status()
                video_bytes = dl_resp.content
        except Exception as exc:
            logger.warning("Failed to download video %s: %s", video_id, exc)
            return {**video, "b1": None, "b2": None, "error": f"download_failed: {exc}"}

        emit(
            "progress",
            {
                "stage": "B",
                "message": f"Video {idx}/{total} downloaded ({len(video_bytes)//1024}KB). Running B1 (Gemini)...",
                "video_index": idx,
            },
        )

        # Pass B1 — Gemini structural analysis
        try:
            b1_data = await _b1_gemini(video_bytes)
        except Exception as exc:
            logger.warning("B1 (Gemini) failed for video %s: %s", video_id, exc)
            return {**video, "b1": None, "b2": None, "error": f"b1_failed: {exc}"}

        emit(
            "progress",
            {
                "stage": "B",
                "message": f"Video {idx}/{total} B1 complete. Running B2 (GPT)...",
                "video_index": idx,
            },
        )

        # Pass B2 — GPT-5.4 pattern extraction
        try:
            b2_data = await _b2_gpt(b1_data)
        except Exception as exc:
            logger.warning("B2 (GPT) failed for video %s: %s", video_id, exc)
            return {**video, "b1": b1_data, "b2": None, "error": f"b2_failed: {exc}"}

        emit(
            "progress",
            {
                "stage": "B",
                "message": f"Video {idx}/{total} analysis complete.",
                "video_index": idx,
            },
        )

        return {**video, "b1": b1_data, "b2": b2_data, "error": None}


async def run(job: dict, emit: Callable) -> None:
    """Stage B: analyze all videos concurrently (max 3 at a time)."""
    videos = job.get("videos", [])
    total = len(videos)

    if not videos:
        emit("progress", {"stage": "B", "message": "No videos to analyze.", "done": True})
        job["analyzed_videos"] = []
        return

    emit(
        "progress",
        {"stage": "B", "message": f"Analyzing {total} videos (max 3 concurrent)..."},
    )

    tasks = [
        analyze_video(video, idx + 1, total, emit)
        for idx, video in enumerate(videos)
    ]
    results = await asyncio.gather(*tasks)

    job["analyzed_videos"] = list(results)

    success_count = sum(1 for r in results if r.get("error") is None)
    emit(
        "progress",
        {
            "stage": "B",
            "message": f"Analysis complete: {success_count}/{total} videos succeeded.",
            "done": True,
            "success_count": success_count,
            "total": total,
        },
    )
