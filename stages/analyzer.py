"""Stage B: Analyzer — calls rl-video-analyzer service for Gemini visual analysis.

Sends each video URL to the deployed rl-video-analyzer API (Apify download +
Gemini 2.5 Flash visual analysis). Falls back to GPT-4o transcript analysis
if the user triggers the "use transcripts" skip button in the UI.

Service: https://rl-video-analyzer-production-117b.up.railway.app
"""
import asyncio
import json
import logging
import os
from typing import Callable

import aiohttp
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

VIDEO_ANALYZER_URL = os.getenv(
    "VIDEO_ANALYZER_URL",
    "https://rl-video-analyzer-production-117b.up.railway.app",
).rstrip("/")
VIDEO_ANALYZER_KEY = os.getenv("VIDEO_ANALYZER_KEY", "")  # x-access-key if set

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# Max concurrent visual analysis jobs sent to the service
VISUAL_SEMAPHORE = asyncio.Semaphore(3)


# ─────────────────────────────────────────────────────────────────────────────
# PROMPT — sent to Gemini via custom_prompt mode
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
      "visual": "<specific: shot type (CLOSE-UP/MEDIUM/WIDE), physical action, text overlay content, transitions, props>",
      "product_integration": null
    }
  ],

  "product_first_appear_second": <int or null>,
  "product_integration_method": "<one of: early_hook | mid_reveal | end_reveal | throughout | never>",
  "cta_text": "<verbatim CTA words or null if none>",
  "cta_type": "<one of: link_in_bio | comment_for_link | direct_shop | discount_code | none>",

  "authority_signals": ["<credentials, trust signals, proof elements used>"],
  "archetype_signals": ["<creator archetype signals: pharmacist | wellness_influencer | fitness_coach | ugc_creator | nurse | nutritionist | mom_lifestyle | beauty_guru | etc>"],
  "signature_phrases": ["<repeated phrases or characteristic expressions>"],

  "setting": "<one of: pharmacy_store_aisle | home_bathroom | home_kitchen | home_bedroom | gym | office | outdoor | studio | other>",
  "full_transcript": "<complete verbatim transcript>",

  "pain_point_clarity": <1-5>,
  "transformation_proof": <true | false>,
  "social_proof_present": <true | false>,
  "coa_lab_present": <true | false>
}

RULES: verbatim speech in script fields, specific camera direction in visual fields,
one beat per scene/topic shift, return ONLY the JSON object."""

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
  "beats": [{"time": "<estimated>", "script": "<verbatim section>", "visual": null, "product_integration": null}],
  "product_first_appear_second": null,
  "product_integration_method": "<one of: early_hook | mid_reveal | end_reveal | throughout | never>",
  "cta_text": "<verbatim CTA or null>",
  "cta_type": "<one of: link_in_bio | comment_for_link | direct_shop | discount_code | none>",
  "authority_signals": ["<credentials or trust signals>"],
  "archetype_signals": ["<creator archetype signals>"],
  "signature_phrases": ["<repeated phrases>"],
  "setting": null,
  "full_transcript": "<full verbatim transcript>",
  "pain_point_clarity": <1-5>,
  "transformation_proof": <true | false>,
  "social_proof_present": <true | false>,
  "coa_lab_present": <true | false>
}"""


# ─────────────────────────────────────────────────────────────────────────────
# VISUAL PATH — rl-video-analyzer service
# ─────────────────────────────────────────────────────────────────────────────

async def _analyze_visual(video: dict, idx: int, total: int, emit: Callable) -> dict:
    """Submit video URL to rl-video-analyzer service; poll until Gemini result arrives."""
    video_id = video.get("video_id", f"video_{idx}")
    tiktok_url = video.get("url") or video.get("download_url") or ""

    if not tiktok_url:
        return {**video, "b1": None, "error": "no_url"}

    headers = {"Content-Type": "application/json"}
    if VIDEO_ANALYZER_KEY:
        headers["x-access-key"] = VIDEO_ANALYZER_KEY

    async with VISUAL_SEMAPHORE:
        emit("progress", {"stage": "B", "message": f"Video {idx}/{total}: submitting for visual analysis…"})
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                # Submit job
                async with session.post(
                    f"{VIDEO_ANALYZER_URL}/api/analyze",
                    json={"urls": [tiktok_url], "mode": "custom", "custom_prompt": B1_VISUAL_PROMPT},
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status != 200:
                        return {**video, "b1": None, "error": f"service_http_{resp.status}"}
                    data = await resp.json()
                    task_id = data.get("task_id")
                    if not task_id:
                        return {**video, "b1": None, "error": "no_task_id"}

                # Poll for completion (max 3 min)
                for _ in range(60):
                    await asyncio.sleep(3)
                    async with session.get(
                        f"{VIDEO_ANALYZER_URL}/api/status/{task_id}",
                        timeout=aiohttp.ClientTimeout(total=10),
                    ) as sresp:
                        status_data = await sresp.json()

                    svc_status = status_data.get("status")
                    progress_label = (status_data.get("progress") or {}).get("label", "")
                    if progress_label:
                        emit("progress", {"stage": "B", "message": f"Video {idx}/{total}: {progress_label}"})

                    if svc_status == "completed":
                        analyses = (status_data.get("result") or {}).get("analyses", [])
                        if not analyses:
                            return {**video, "b1": None, "error": "analysis_empty"}
                        b1 = analyses[0]
                        b1["_source"] = "gemini_visual"
                        emit("progress", {
                            "stage": "B",
                            "message": f"Video {idx}/{total} ✓ visual — {b1.get('hook_type', '?')} / {b1.get('pain_point', '?')}",
                        })
                        return {**video, "b1": b1, "error": None}

                    if svc_status == "error":
                        return {**video, "b1": None, "error": status_data.get("error", "service_error")}

                return {**video, "b1": None, "error": "timeout"}

        except Exception as e:
            logger.warning("Visual analysis failed for %s: %s", video_id, e)
            return {**video, "b1": None, "error": f"service_error: {e}"}


# ─────────────────────────────────────────────────────────────────────────────
# TRANSCRIPT PATH — GPT-4o fallback (user-triggered via UI skip button)
# ─────────────────────────────────────────────────────────────────────────────

async def _analyze_transcript(video: dict, idx: int, total: int, emit: Callable) -> dict:
    """Analyze using Stage A transcript via GPT-4o (user-triggered fallback)."""
    video_id = video.get("video_id", f"video_{idx}")
    transcript = (video.get("transcript") or "").strip()

    if not transcript:
        return {**video, "b1": None, "error": "no_transcript"}

    emit("progress", {"stage": "B", "message": f"Video {idx}/{total}: transcript analysis…"})
    try:
        resp = await openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": f"{B1_TRANSCRIPT_PROMPT}\n\nTRANSCRIPT:\n{transcript}"}],
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
        logger.warning("Transcript analysis failed for %s: %s", video_id, e)
        return {**video, "b1": None, "error": f"transcript_failed: {e}"}


# ─────────────────────────────────────────────────────────────────────────────
# STAGE B ORCHESTRATOR
# ─────────────────────────────────────────────────────────────────────────────

async def run(job: dict, emit: Callable) -> None:
    """Stage B: visual analysis via rl-video-analyzer service (3 concurrent).

    job["use_transcripts"] = True  →  user hit the skip button; use GPT-4o transcript mode.
    """
    videos = job.get("videos", [])
    if not videos:
        emit("progress", {"stage": "B", "message": "No videos to analyze.", "done": True})
        job["analyzed_videos"] = []
        return

    total = len(videos)
    use_transcripts = job.get("use_transcripts", False)

    if use_transcripts:
        emit("progress", {"stage": "B", "message": f"Transcript mode — analyzing {total} videos…"})
        analyze_fn = _analyze_transcript
    else:
        emit("progress", {"stage": "B", "message": f"Visual analysis — {total} videos via Gemini…"})
        analyze_fn = _analyze_visual

    tasks = [analyze_fn(v, i + 1, total, emit) for i, v in enumerate(videos)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    analyzed = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            analyzed.append({**videos[i], "b1": None, "error": str(result)})
        else:
            analyzed.append(result)

    job["analyzed_videos"] = analyzed
    successful = sum(1 for r in analyzed if r.get("b1") is not None)
    source = "transcript" if use_transcripts else "visual"

    emit("progress", {
        "stage": "B",
        "message": f"Analysis complete — {successful}/{total} videos ({source})",
        "done": True,
    })
    logger.info("Stage B complete: %d/%d videos (%s)", successful, total, source)
