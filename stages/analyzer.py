"""Stage B: Analyzer — GPT-4o transcript pattern analysis.

Transcripts come from Stage A (Apify batch scrape) — no per-video download needed.
Railway runs on a datacenter IP that TikTok CDN blocks. The MCP works locally
because it runs on a residential Mac IP. Solution: use transcripts from Stage A directly.

Model: GPT-4o for all transcript analysis (~2s/video, all concurrent).
"""
import asyncio
import json
import logging
import os
from typing import Callable

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)


# ─────────────────────────────────────────────────────────────────────────────
# TRANSCRIPT ANALYSIS PROMPT
# ─────────────────────────────────────────────────────────────────────────────

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
      "product_integration": null
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
# STAGE B PIPELINE
# ─────────────────────────────────────────────────────────────────────────────

async def _analyze_one(video: dict, idx: int, total: int, emit: Callable) -> dict:
    """Analyze one video using its transcript from Stage A."""
    video_id = video.get("video_id", f"video_{idx}")
    transcript = (video.get("transcript") or "").strip()

    if not transcript:
        return {**video, "b1": None, "error": "no_transcript"}

    emit("progress", {"stage": "B", "message": f"Video {idx}/{total}: analyzing transcript..."})
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
            "message": f"Video {idx}/{total} ✓ — {b1.get('hook_type', '?')} / {b1.get('pain_point', '?')}",
        })
        return {**video, "b1": b1, "error": None}

    except Exception as e:
        logger.warning("Transcript analysis failed for %s: %s", video_id, e)
        return {**video, "b1": None, "error": f"transcript_failed: {e}"}


async def run(job: dict, emit: Callable) -> None:
    """Stage B: analyze all videos via transcript (~2s/video, all concurrent)."""
    videos = job.get("videos", [])
    if not videos:
        emit("progress", {"stage": "B", "message": "No videos to analyze.", "done": True})
        job["analyzed_videos"] = []
        return

    total = len(videos)
    has_transcripts = sum(1 for v in videos if (v.get("transcript") or "").strip())
    emit("progress", {
        "stage": "B",
        "message": f"Analyzing {total} videos ({has_transcripts} with transcripts)…",
    })

    tasks = [_analyze_one(v, i + 1, total, emit) for i, v in enumerate(videos)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    analyzed = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            analyzed.append({**videos[i], "b1": None, "error": str(result)})
        else:
            analyzed.append(result)

    job["analyzed_videos"] = analyzed
    successful = sum(1 for r in analyzed if r.get("b1") is not None)

    emit("progress", {
        "stage": "B",
        "message": f"Analysis complete — {successful}/{total} videos",
        "done": True,
    })
    logger.info("Stage B complete: %d/%d videos with transcripts", successful, total)
