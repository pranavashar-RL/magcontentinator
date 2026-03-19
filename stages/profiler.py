"""Stage C: Profiler — GPT-5.4 creator archetype + identity profile from analyzed videos."""
import os
import json
import logging
from collections import Counter
from typing import Callable

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

PROFILER_SYSTEM = """You are an expert TikTok creator profiler. Your job is to analyze a creator's video patterns and produce an accurate profile.
Return ONLY valid JSON. No markdown."""

OUTPUT_SCHEMA = """{
  "archetype": "<primary archetype: pharmacist|nurse|health_educator|nutrition_coach|doctor|wellness_influencer|mom_lifestyle|beauty_guru|lifestyle|fitness_influencer|fitness_coach|athlete|deal_hunter|deal_announcer|product_reviewer|tiktok_shop_affiliate|ugc_creator|everyday_consumer|authentic_testimonial_giver|blue_collar_worker_persona|rural_lifestyle_influencer|fatherly_advisor|reaction_creator|relatable_storyteller>",
  "archetype_confidence": <0.0-1.0>,
  "secondary_archetypes": ["<up to 2>"],
  "dominant_hook_types": ["<top 3 hooks this creator uses>"],
  "dominant_narratives": ["<top 2 narratives>"],
  "dominant_pain_points": ["<top 3 pain points they address>"],
  "avg_video_duration": "<e.g. 45-60s>",
  "authority_level": "<none|low|medium|high|expert>",
  "transformation_proof_rate": <0.0-1.0>,
  "social_proof_rate": <0.0-1.0>,
  "identity_constants": {
    "credential": "<their key credential/expertise if any, else null>",
    "setting": "<typical filming setting>",
    "presentation_style": "<e.g. direct-to-camera, educational, storytelling>",
    "energy_level": "<calm|moderate|high|intense>",
    "audience_relationship": "<peer|authority|friend|entertainer>"
  },
  "strengths": ["<up to 3 content strengths>"],
  "gaps": ["<up to 3 content gaps vs AshwaMag best practices>"]
}"""


def _build_user_prompt(analyzed_videos: list) -> str:
    """Summarise all analyzed video patterns into a prompt for the profiler.
    B1 now contains all pattern fields (hook_type, narrative_arc, etc.) — no separate B2.
    """
    valid = [v for v in analyzed_videos if v.get("b1") is not None]
    total = len(analyzed_videos)
    valid_count = len(valid)

    if not valid:
        raise ValueError("No successfully analyzed videos to profile.")

    # Aggregate counts for each categorical field
    hook_types = Counter(v["b1"].get("hook_type", "") for v in valid if v["b1"].get("hook_type"))
    narratives = Counter(v["b1"].get("narrative_arc", "") for v in valid if v["b1"].get("narrative_arc"))
    pain_points = Counter(v["b1"].get("pain_point", "") for v in valid if v["b1"].get("pain_point"))
    cta_types = Counter(v["b1"].get("cta_type", "") for v in valid if v["b1"].get("cta_type"))
    prod_methods = Counter(
        v["b1"].get("product_integration_method", "") for v in valid
        if v["b1"].get("product_integration_method")
    )

    # Authority signals — flatten all lists
    all_authority = []
    for v in valid:
        all_authority.extend(v["b1"].get("authority_signals", []))
    authority_counter = Counter(all_authority)

    # Archetype signals — flatten all lists
    all_archetype_signals = []
    for v in valid:
        all_archetype_signals.extend(v["b1"].get("archetype_signals", []))
    archetype_counter = Counter(all_archetype_signals)

    # Transformation & social proof rates
    transformation_count = sum(1 for v in valid if v["b1"].get("transformation_proof") is True)
    social_proof_count = sum(1 for v in valid if v["b1"].get("social_proof_present") is True)
    coa_count = sum(1 for v in valid if v["b1"].get("coa_lab_present") is True)

    # Pain point clarity average
    clarity_scores = [v["b1"].get("pain_point_clarity", 0) for v in valid if v["b1"].get("pain_point_clarity")]
    avg_clarity = sum(clarity_scores) / len(clarity_scores) if clarity_scores else 0

    # Video durations
    durations = [
        v["b1"].get("duration_seconds", 0)
        for v in valid
        if v["b1"].get("duration_seconds", 0) > 0
    ]
    avg_duration = int(sum(durations) / len(durations)) if durations else 0

    # Per-video summary
    video_summaries = []
    for i, v in enumerate(valid, 1):
        b1 = v["b1"]
        hook_text = (b1.get("hook_text") or "")[:120]
        source = b1.get("_source", "unknown")
        video_summaries.append(
            f"  Video {i} [{source}]: hook={b1.get('hook_type')} | narrative={b1.get('narrative_arc')} | "
            f"pain={b1.get('pain_point')} | cta={b1.get('cta_type')} | "
            f"product_method={b1.get('product_integration_method')} | "
            f"transform={b1.get('transformation_proof')} | social_proof={b1.get('social_proof_present')} | "
            f"clarity={b1.get('pain_point_clarity')} | "
            f"hook_text=\"{hook_text}\""
        )

    lines = [
        f"Creator has {valid_count} successfully analyzed videos (out of {total} total).",
        f"Average video duration: {avg_duration}s",
        f"",
        f"HOOK TYPES (most common first): {dict(hook_types.most_common(6))}",
        f"NARRATIVE ARCS: {dict(narratives.most_common(5))}",
        f"PAIN POINTS: {dict(pain_points.most_common(6))}",
        f"CTA TYPES: {dict(cta_types.most_common(4))}",
        f"PRODUCT INTEGRATION METHODS: {dict(prod_methods.most_common(5))}",
        f"",
        f"AUTHORITY SIGNALS (all mentions): {dict(authority_counter.most_common(10))}",
        f"ARCHETYPE SIGNALS (all mentions): {dict(archetype_counter.most_common(10))}",
        f"",
        f"TRANSFORMATION PROOF: {transformation_count}/{valid_count} videos ({transformation_count/valid_count:.0%})",
        f"SOCIAL PROOF PRESENT: {social_proof_count}/{valid_count} videos ({social_proof_count/valid_count:.0%})",
        f"COA/LAB RESULTS SHOWN: {coa_count}/{valid_count} videos",
        f"AVG PAIN POINT CLARITY: {avg_clarity:.1f}/5",
        f"",
        f"PER-VIDEO BREAKDOWN:",
        *video_summaries,
        f"",
        f"Based on the above, produce a complete creator profile. Return JSON matching this exact schema:",
        OUTPUT_SCHEMA,
    ]
    return "\n".join(lines)


def _parse_json_response(text: str) -> dict:
    """Strip markdown fences if present and parse JSON."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text[: text.rfind("```")]
    return json.loads(text.strip())


async def run(job: dict, emit: Callable) -> None:
    """Stage C: build creator profile from all analyzed videos."""
    analyzed_videos = job.get("analyzed_videos", [])

    emit("progress", {"stage": "C", "message": "Building creator profile..."})

    valid_count = sum(1 for v in analyzed_videos if v.get("b1") is not None)
    if valid_count == 0:
        raise RuntimeError("Stage C: no analyzed videos — cannot profile creator.")

    user_prompt = _build_user_prompt(analyzed_videos)

    response = await openai_client.chat.completions.create(
        model="gpt-5.4",
        messages=[
            {"role": "system", "content": PROFILER_SYSTEM},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
    )

    raw_text = response.choices[0].message.content
    profile = _parse_json_response(raw_text)

    job["profile"] = profile

    emit(
        "progress",
        {
            "stage": "C",
            "message": (
                f"Profile complete: {profile.get('archetype', 'unknown')} "
                f"(confidence {profile.get('archetype_confidence', 0):.0%})"
            ),
            "done": True,
            "archetype": profile.get("archetype"),
            "confidence": profile.get("archetype_confidence"),
        },
    )
