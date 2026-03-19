"""Stage B: Analyzer — Gemini 2.5 Flash visual beat analysis (merged B1+B2 in one shot).

Video download: Apify postURLs per video (bypasses Railway/TikTok CDN block, gets fresh URL).
Gemini: new google.genai SDK, response_mime_type=application/json, thinking budget, file cleanup.
GPT-4o fallback: transcript-only analysis when video download or Gemini fails.

Model assignments:
  - Gemini 2.5 Flash: visual analysis (all video analysis)
  - GPT-4o: transcript-only fallback
"""
import os
import asyncio
import json
import logging
import tempfile
import time
from typing import Callable, Optional

from apify_client import ApifyClient
from google import genai
from google.genai import types
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
APIFY_API_KEY = os.getenv("APIFY_API_KEY", "")
APIFY_ACTOR_ID = os.getenv("APIFY_ACTOR_ID", "z6GDWcyb4ZVT10ogS")

gemini_client = genai.Client(api_key=GOOGLE_API_KEY)
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# Gemini: 2 concurrent uploads (memory/GPU bound)
# Apify downloads: 3 concurrent (API rate limit friendly)
GEMINI_SEMAPHORE = asyncio.Semaphore(2)
APIFY_SEMAPHORE = asyncio.Semaphore(3)

GEMINI_THINKING_BUDGET = 4096  # Enough for careful visual analysis, not overkill


# ─────────────────────────────────────────────────────────────────────────────
# OPTIMIZED 20-FIELD PROMPT — merges B1 visual analysis + B2 pattern extraction
# Gemini watches the video directly → more accurate classification than GPT-4o
# reading a text summary
# ─────────────────────────────────────────────────────────────────────────────

B1_VISUAL_PROMPT = """You are analyzing a TikTok video for content strategy research.
Watch the ENTIRE video carefully — hook, narrative, product reveal, CTA.

Return ONLY valid JSON with exactly these fields. No markdown fences, no extra text.

{
  "duration_seconds": <int: total video length>,

  "hook_text": "<verbatim exact words spoken in the first 3 seconds>",
  "hook_visual": "<specific: setting, shot type, framing, props held, body language, text overlay visible in the opening>",
  "hook_type": "<one of: controversial_take | bold_claim | authority_intro | relatable_callout | curiosity_gap | question | before_after | personal_story | social_proof_callout | fomo_urgency | shock_value | negative_framing>",
  "hook_scroll_stop": "<one sentence: the single most attention-grabbing element in the first 2 seconds>",

  "narrative_arc": "<one of: problem_solution | testimonial | before_after | comparison | authority_lecture | listicle | debunk | social_proof_cascade | tutorial | enemy_hero>",
  "pain_point": "<one of: sleep | brain_fog | stress_cortisol | low_energy | muscle_recovery | pms_hormones | general_wellness | other>",

  "beats": [
    {
      "time": "<e.g. 0-3s>",
      "script": "<VERBATIM words spoken in this beat — exact speech, not a summary>",
      "visual": "<specific: shot type (CLOSE-UP/MEDIUM/WIDE), physical action, text overlay content, transitions, props — NOT generic>",
      "product_integration": <null | "first_appearance" | "on_screen" | "demo" | "verbal_only">
    }
  ],

  "product_first_appear_second": <int or null: exact second product appears on screen>,
  "product_integration_method": "<one of: early_hook | mid_reveal | end_reveal | throughout | never>",
  "cta_text": "<verbatim CTA words or null if none>",
  "cta_type": "<one of: link_in_bio | comment_for_link | direct_shop | discount_code | none>",

  "authority_signals": ["<list credentials, trust signals, or proof elements used>"],
  "archetype_signals": ["<creator archetype signals: pharmacist | wellness_influencer | fitness_coach | ugc_creator | nurse | nutritionist | mom_lifestyle | beauty_guru | etc>"],
  "signature_phrases": ["<repeated phrases, catchphrases, or characteristic expressions>"],

  "setting": "<one of: pharmacy_store_aisle | home_bathroom | home_kitchen | home_bedroom | gym | office | outdoor | studio | other>",
  "full_transcript": "<complete verbatim transcript — every word spoken from first to last>",

  "pain_point_clarity": <1-5: how clearly is a specific problem articulated>,
  "transformation_proof": <true | false: is before/after or results evidence shown>,
  "social_proof_present": <true | false: reviews, comments, or testimonials shown>,
  "coa_lab_present": <true | false: COA, lab results, or third-party testing shown>
}

CRITICAL RULES:
1. Every "script" field: verbatim speech, exact words — never paraphrase or summarize
2. Every "visual" field: specific camera direction (e.g. "CLOSE-UP of beadlets in palm, text overlay: VISIBLE BEADLETS") — not generic ("shows product")
3. One beat per topic/scene shift — capture all of them
4. hook_text: literally the first words the creator says, verbatim
5. Return ONLY the JSON object. No explanation, no markdown."""


# ─── Transcript-only B1 fallback (GPT-4o when video download fails) ───

B1_TRANSCRIPT_PROMPT = """You are analyzing a TikTok video transcript for content strategy research.
Given this transcript, reconstruct the content structure and classify the patterns.
Return ONLY valid JSON with exactly these fields. No markdown fences.

{
  "duration_seconds": null,
  "hook_text": "<opening line verbatim from transcript>",
  "hook_visual": null,
  "hook_type": "<one of: controversial_take | bold_claim | authority_intro | relatable_callout | curiosity_gap | question | before_after | personal_story | social_proof_callout | fomo_urgency | shock_value | negative_framing>",
  "hook_scroll_stop": "<what about the opening would stop a scroll>",
  "narrative_arc": "<one of: problem_solution | testimonial | before_after | comparison | authority_lecture | listicle | debunk | social_proof_cascade | tutorial | enemy_hero>",
  "pain_point": "<one of: sleep | brain_fog | stress_cortisol | low_energy | muscle_recovery | pms_hormones | general_wellness | other>",
  "beats": [
    {
      "time": "<estimated>",
      "script": "<verbatim section of transcript>",
      "visual": null,
      "product_integration": <null | "first_appearance" | "on_screen" | "demo" | "verbal_only">
    }
  ],
  "product_first_appear_second": null,
  "product_integration_method": "<one of: early_hook | mid_reveal | end_reveal | throughout | never>",
  "cta_text": "<verbatim CTA if present or null>",
  "cta_type": "<one of: link_in_bio | comment_for_link | direct_shop | discount_code | none>",
  "authority_signals": ["<credentials or trust signals mentioned>"],
  "archetype_signals": ["<inferred creator archetype signals>"],
  "signature_phrases": ["<repeated phrases or characteristic expressions>"],
  "setting": null,
  "full_transcript": "<full verbatim transcript>",
  "pain_point_clarity": <1-5>,
  "transformation_proof": <true | false>,
  "social_proof_present": <true | false>,
  "coa_lab_present": <true | false>
}"""


# ─────────────────────────────────────────────────────────────────────────────
# APIFY DOWNLOAD — per-video, fresh CDN URL at analysis time
# Bypasses Railway IP block by letting Apify fetch fresh CDN URLs
# ─────────────────────────────────────────────────────────────────────────────

def _apify_download_video_sync(tiktok_url: str, output_path: str) -> bool:
    """Download a single TikTok video via Apify postURLs (sync, runs in executor).

    Gets a fresh CDN URL at analysis time (not the expiring URL from Stage A),
    then downloads bytes directly.
    """
    try:
        client = ApifyClient(APIFY_API_KEY)
        actor_run = client.actor(APIFY_ACTOR_ID).call(
            run_input={"postURLs": [tiktok_url], "resultsPerPage": 1},
            max_items=1,
        )
        dataset_id = actor_run.get("defaultDatasetId")
        if not dataset_id:
            return False

        items = list(client.dataset(dataset_id).iterate_items())
        if not items:
            return False

        item = items[0]
        video_url = (
            item.get("videoUrl")
            or item.get("video", {}).get("downloadAddr")
            or item.get("videoPlayUrl")
        )
        if not video_url:
            return False

        import requests as req
        resp = req.get(video_url, timeout=90, stream=True)
        if resp.status_code != 200:
            return False

        with open(output_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        # Sanity check: must be a real video (>50KB)
        return os.path.exists(output_path) and os.path.getsize(output_path) > 50_000

    except Exception as e:
        logger.warning("Apify download failed for %s: %s", tiktok_url, e)
        return False


# ─────────────────────────────────────────────────────────────────────────────
# GEMINI ANALYSIS — new SDK, response_mime_type=json, thinking budget, cleanup
# ─────────────────────────────────────────────────────────────────────────────

def _gemini_analyze_sync(video_path: str) -> dict:
    """Upload to Gemini, generate analysis, delete file. Sync — runs in executor."""
    gemini_file = None
    try:
        gemini_file = gemini_client.files.upload(
            file=video_path,
            config={"mime_type": "video/mp4"},
        )

        # Poll until ACTIVE (max 120s)
        for _ in range(60):
            if gemini_file.state.name == "ACTIVE":
                break
            if gemini_file.state.name == "FAILED":
                raise RuntimeError("Gemini file processing FAILED")
            time.sleep(2)
            gemini_file = gemini_client.files.get(name=gemini_file.name)
        else:
            raise RuntimeError("Gemini file never became ACTIVE after 120s")

        gen_config = types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.1,
            max_output_tokens=8192,
            thinking_config=types.ThinkingConfig(thinking_budget=GEMINI_THINKING_BUDGET),
        )

        response = gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                types.Part.from_uri(file_uri=gemini_file.uri, mime_type="video/mp4"),
                B1_VISUAL_PROMPT,
            ],
            config=gen_config,
        )

        return json.loads(response.text)

    finally:
        # Always clean up — don't leave files sitting in Gemini storage
        if gemini_file:
            try:
                gemini_client.files.delete(name=gemini_file.name)
            except Exception:
                pass


# ─────────────────────────────────────────────────────────────────────────────
# STAGE B PIPELINE — download + analyze + fallback
# ─────────────────────────────────────────────────────────────────────────────

async def _analyze_video(video: dict, idx: int, total: int, emit: Callable) -> dict:
    """Full pipeline for one video: Apify download → Gemini visual analysis.
    Falls back to GPT-4o transcript analysis if download or Gemini fails.
    """
    video_id = video.get("video_id", f"video_{idx}")
    tiktok_url = video.get("url") or video.get("download_url") or ""
    transcript = (video.get("transcript") or "").strip()

    if not tiktok_url:
        logger.warning("Video %s has no URL", video_id)
        return {**video, "b1": None, "error": "no_url"}

    # ── Phase 1: Download via Apify ──
    async with APIFY_SEMAPHORE:
        emit("progress", {"stage": "B", "message": f"Video {idx}/{total}: downloading via Apify..."})
        tmp_path = tempfile.mktemp(suffix=".mp4")
        try:
            loop = asyncio.get_event_loop()
            success = await asyncio.wait_for(
                loop.run_in_executor(None, _apify_download_video_sync, tiktok_url, tmp_path),
                timeout=120,
            )
        except Exception as e:
            logger.warning("Download failed for %s: %s", video_id, e)
            success = False

    # ── Phase 2a: Gemini visual analysis (if download succeeded) ──
    if success:
        size_kb = os.path.getsize(tmp_path) // 1024
        emit("progress", {"stage": "B", "message": f"Video {idx}/{total}: {size_kb}KB — analyzing with Gemini..."})

        async with GEMINI_SEMAPHORE:
            try:
                loop = asyncio.get_event_loop()
                b1 = await asyncio.wait_for(
                    loop.run_in_executor(None, _gemini_analyze_sync, tmp_path),
                    timeout=240,
                )
                b1["_source"] = "gemini_visual"
            except Exception as e:
                logger.warning("Gemini analysis failed for %s: %s", video_id, e)
                b1 = None
            finally:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

        if b1:
            emit("progress", {
                "stage": "B",
                "message": f"Video {idx}/{total} ✓ visual — {b1.get('hook_type', '?')} / {b1.get('pain_point', '?')}",
            })
            return {**video, "b1": b1, "error": None}

    # ── Phase 2b: Transcript fallback (GPT-4o) ──
    try:
        os.unlink(tmp_path)
    except OSError:
        pass

    if not transcript:
        return {**video, "b1": None, "error": "download_failed_no_transcript"}

    emit("progress", {"stage": "B", "message": f"Video {idx}/{total}: transcript fallback..."})
    try:
        resp = await openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{
                "role": "user",
                "content": f"{B1_TRANSCRIPT_PROMPT}\n\nTRANSCRIPT:\n{transcript}",
            }],
            temperature=0.1,
            max_completion_tokens=3000,
            timeout=60,
        )
        b1 = json.loads(resp.choices[0].message.content)
        b1["_source"] = "gpt4o_transcript"
        if not b1.get("full_transcript"):
            b1["full_transcript"] = transcript

        emit("progress", {
            "stage": "B",
            "message": f"Video {idx}/{total} ✓ transcript — {b1.get('hook_type', '?')} / {b1.get('pain_point', '?')}",
        })
        return {**video, "b1": b1, "error": None}

    except Exception as e:
        logger.warning("Transcript fallback failed for %s: %s", video_id, e)
        return {**video, "b1": None, "error": f"transcript_failed: {e}"}


async def run(job: dict, emit: Callable) -> None:
    """Stage B: analyze all videos concurrently (Gemini ≤2 at a time, Apify ≤3)."""
    videos = job.get("videos", [])
    if not videos:
        emit("progress", {"stage": "B", "message": "No videos to analyze.", "done": True})
        job["analyzed_videos"] = []
        return

    total = len(videos)
    emit("progress", {"stage": "B", "message": f"Starting visual analysis of {total} videos..."})

    tasks = [_analyze_video(v, i + 1, total, emit) for i, v in enumerate(videos)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    analyzed = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            analyzed.append({**videos[i], "b1": None, "error": str(result)})
        else:
            analyzed.append(result)

    job["analyzed_videos"] = analyzed
    successful = sum(1 for r in analyzed if r.get("b1") is not None)
    visual = sum(1 for r in analyzed if r.get("b1", {}) and r["b1"].get("_source") == "gemini_visual")
    fallback = successful - visual

    emit("progress", {
        "stage": "B",
        "message": f"Analysis complete — {successful}/{total} videos ({visual} visual, {fallback} transcript fallback)",
        "done": True,
    })
    logger.info("Stage B complete: %d/%d videos (%d visual, %d transcript)", successful, total, visual, fallback)
