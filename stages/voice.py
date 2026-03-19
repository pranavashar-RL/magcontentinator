"""Stage D: Voice — GPT-5.4 voice fingerprint from top-5 transcripts + profile context."""
import os
import json
import logging
from typing import Callable

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

VOICE_SYSTEM = """You are a voice fingerprinting expert for TikTok content creators.
Analyze the creator's speech patterns, vocabulary, and communication style.
Return ONLY valid JSON. No markdown."""

OUTPUT_SCHEMA = """{
  "tone": "<e.g. authoritative-but-approachable, casual-educational, hype-energy>",
  "vocabulary_level": "<simple|moderate|technical|mixed>",
  "signature_phrases": ["<up to 5 phrases this creator actually uses>"],
  "speaking_pace": "<slow|moderate|fast|variable>",
  "hook_style": "<how they open videos>",
  "cta_style": "<how they close and drive action>",
  "educational_style": "<how they explain concepts>",
  "authenticity_markers": ["<what makes them sound genuine>"],
  "avoid": ["<speech patterns to avoid to stay true to voice>"],
  "example_hook_in_their_voice": "<write one example hook for AshwaMag in their exact voice>",
  "example_cta_in_their_voice": "<write one example CTA for AshwaMag in their exact voice>"
}"""


def _parse_json_response(text: str) -> dict:
    """Strip markdown fences if present and parse JSON."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text[: text.rfind("```")]
    return json.loads(text.strip())


def _build_user_prompt(analyzed_videos: list, profile: dict) -> str:
    """Build the voice fingerprinting prompt from top-5 transcripts and profile."""
    # Sort videos by views descending, take top 5
    sorted_videos = sorted(
        analyzed_videos,
        key=lambda v: v.get("views", 0),
        reverse=True,
    )
    top5 = sorted_videos[:5]

    # Extract transcripts from B1 data
    transcripts = []
    for v in top5:
        b1 = v.get("b1") or {}
        transcript = b1.get("transcript", "").strip()
        if not transcript:
            # Fall back to concatenating beat audio lines
            beats = b1.get("beats", [])
            audio_lines = [
                b.get("audio", "") for b in beats if b.get("audio")
            ]
            transcript = " ".join(audio_lines).strip()

        if transcript:
            transcripts.append(
                {
                    "video_id": v.get("video_id", ""),
                    "views": v.get("views", 0),
                    "hook_text": b1.get("hook_text", ""),
                    "transcript": transcript[:2000],  # cap at 2000 chars per video
                }
            )

    if not transcripts:
        raise ValueError("Stage D: no transcripts available for voice fingerprinting.")

    # Profile context
    archetype = profile.get("archetype", "unknown")
    secondary = profile.get("secondary_archetypes", [])
    authority_level = profile.get("authority_level", "unknown")
    identity = profile.get("identity_constants", {})
    presentation_style = identity.get("presentation_style", "")
    energy_level = identity.get("energy_level", "")
    credential = identity.get("credential", "none")
    audience_rel = identity.get("audience_relationship", "")
    dominant_hooks = profile.get("dominant_hook_types", [])
    dominant_narratives = profile.get("dominant_narratives", [])

    lines = [
        "CREATOR PROFILE CONTEXT:",
        f"  Archetype: {archetype} (secondary: {', '.join(secondary) if secondary else 'none'})",
        f"  Authority level: {authority_level}",
        f"  Credential: {credential}",
        f"  Presentation style: {presentation_style}",
        f"  Energy level: {energy_level}",
        f"  Audience relationship: {audience_rel}",
        f"  Dominant hook types: {dominant_hooks}",
        f"  Dominant narrative arcs: {dominant_narratives}",
        "",
        f"TOP {len(transcripts)} VIDEOS BY VIEWS (transcripts):",
    ]

    for i, t in enumerate(transcripts, 1):
        lines.append(f"\n--- Video {i} ({t['views']:,} views) ---")
        if t["hook_text"]:
            lines.append(f"Hook (first 3s): \"{t['hook_text']}\"")
        lines.append(f"Full transcript:\n{t['transcript']}")

    lines += [
        "",
        "Based on the transcripts above and the creator profile context, produce a precise voice fingerprint.",
        "Pay special attention to:",
        "  - Actual phrases and sentence structures the creator uses",
        "  - How they address the audience (you, girl, bestie, guys, etc.)",
        "  - How they structure their hooks and CTAs",
        "  - Their vocabulary complexity and preferred terminology",
        "  - What makes their voice feel authentic vs. scripted",
        "",
        "The example_hook_in_their_voice and example_cta_in_their_voice fields should be for AshwaMag Gummies",
        "(magnesium + ashwagandha supplement targeting women). Write them in the creator's EXACT voice —",
        "same vocabulary, cadence, and style as shown in the transcripts above.",
        "",
        "Return JSON matching this exact schema:",
        OUTPUT_SCHEMA,
    ]

    return "\n".join(lines)


async def run(job: dict, emit: Callable) -> None:
    """Stage D: create voice fingerprint from top-5 transcripts + profile context."""
    analyzed_videos = job.get("analyzed_videos", [])
    profile = job.get("profile", {})

    emit("progress", {"stage": "D", "message": "Building voice fingerprint..."})

    if not analyzed_videos:
        raise RuntimeError("Stage D: no analyzed videos in job state.")
    if not profile:
        raise RuntimeError("Stage D: profile missing from job state — run Stage C first.")

    # Count how many videos have usable transcripts
    transcript_count = sum(
        1 for v in analyzed_videos
        if (v.get("b1") or {}).get("transcript")
        or any(b.get("audio") for b in (v.get("b1") or {}).get("beats", []))
    )

    if transcript_count == 0:
        raise RuntimeError("Stage D: no transcripts found in analyzed videos.")

    emit(
        "progress",
        {
            "stage": "D",
            "message": f"Found {transcript_count} videos with transcripts. Fingerprinting voice...",
        },
    )

    user_prompt = _build_user_prompt(analyzed_videos, profile)

    response = await openai_client.chat.completions.create(
        model="gpt-5.4",
        messages=[
            {"role": "system", "content": VOICE_SYSTEM},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.4,
    )

    raw_text = response.choices[0].message.content
    voice = _parse_json_response(raw_text)

    job["voice"] = voice

    emit(
        "progress",
        {
            "stage": "D",
            "message": (
                f"Voice fingerprint complete: {voice.get('tone', 'unknown')} tone, "
                f"{voice.get('vocabulary_level', 'unknown')} vocabulary."
            ),
            "done": True,
            "tone": voice.get("tone"),
            "vocabulary_level": voice.get("vocabulary_level"),
        },
    )
