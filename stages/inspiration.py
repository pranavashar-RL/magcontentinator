"""Stage: Inspiration — analyze inspiration videos + create creator-specific digest."""
import os
import asyncio
import httpx
import tempfile
from typing import Callable, Optional

import google.generativeai as genai
from openai import AsyncOpenAI

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
genai.configure(api_key=GOOGLE_API_KEY)
client = AsyncOpenAI(api_key=OPENAI_API_KEY)

GEMINI_MODEL = "gemini-2.0-flash"
GPT_MODEL = "gpt-5.4"

GEMINI_BEAT_PROMPT = """Analyze this TikTok video beat by beat for content strategy research.
Focus on: hook technique, narrative arc, product integration timing, CTA method, key claims made.
Return a concise analysis paragraph (not JSON), 100-150 words."""

DIGEST_SYSTEM = """You are an expert TikTok content strategist for supplement brands.
You have analyzed inspiration videos and you understand the creator's archetype and voice.
Your task: write a compatibility digest — a clear, practical guide for what angles and techniques
from the inspiration videos could work for THIS specific creator, and exactly how to adapt them.
Be specific. Name the techniques. Explain why they fit (or don't). 200-300 words max."""


async def analyze_inspiration_video(url: str) -> Optional[str]:
    """Download and analyze one inspiration video with Gemini Flash."""
    try:
        # Download video to a temp file
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as http:
            resp = await http.get(url)
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "video/mp4")
            # Normalize MIME type — Gemini needs a proper video/* type
            if "video" not in content_type:
                content_type = "video/mp4"

        suffix = ".mp4"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(resp.content)
            tmp_path = tmp.name

        try:
            # Upload to Gemini
            uploaded = genai.upload_file(path=tmp_path, mime_type=content_type)

            # Poll until the file is ACTIVE
            for _ in range(30):
                file_state = genai.get_file(uploaded.name)
                if file_state.state.name == "ACTIVE":
                    break
                if file_state.state.name == "FAILED":
                    return None
                await asyncio.sleep(2)
            else:
                return None

            # Generate beat analysis
            model = genai.GenerativeModel(
                model_name=GEMINI_MODEL,
                safety_settings=[
                    {"category": c, "threshold": "BLOCK_NONE"}
                    for c in [
                        "HARM_CATEGORY_HARASSMENT",
                        "HARM_CATEGORY_HATE_SPEECH",
                        "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                        "HARM_CATEGORY_DANGEROUS_CONTENT",
                    ]
                ],
            )
            response = model.generate_content([uploaded, GEMINI_BEAT_PROMPT])
            return response.text.strip() if response.text else None

        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    except Exception as exc:
        # Bad URL or download failure — skip this video
        print(f"[inspiration] Failed to analyze {url}: {exc}")
        return None


async def run(job: dict, emit: Callable) -> None:
    """Analyze inspiration URLs (if any) and produce a creator-specific compatibility digest."""
    urls: list[str] = job.get("inspiration_urls") or []
    note: str = job.get("inspiration_note") or ""
    profile: dict = job.get("profile") or {}
    voice: dict = job.get("voice") or {}

    # Nothing to do
    if not urls and not note.strip():
        job["inspiration_digest"] = None
        emit("progress", {
            "stage": "INSP",
            "message": "No inspiration URLs or note provided. Skipping.",
            "done": True,
        })
        return

    emit("progress", {"stage": "INSP", "message": f"Analyzing {len(urls)} inspiration video(s)..."})

    # Analyze each URL in parallel
    video_analyses: list[str] = []
    if urls:
        tasks = [analyze_inspiration_video(u) for u in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                emit("progress", {"stage": "INSP", "message": f"Skipped URL {i+1}: error during analysis."})
                continue
            if result:
                video_analyses.append(f"[Video {i+1}]\n{result}")
            else:
                emit("progress", {"stage": "INSP", "message": f"Skipped URL {i+1}: could not analyze."})

    if not video_analyses and not note.strip():
        job["inspiration_digest"] = None
        emit("progress", {
            "stage": "INSP",
            "message": "No usable inspiration data after analysis. Skipping digest.",
            "done": True,
        })
        return

    emit("progress", {
        "stage": "INSP",
        "message": f"Analyzed {len(video_analyses)} video(s). Generating compatibility digest...",
    })

    # Build creator context for the digest prompt
    archetype = profile.get("archetype", "unknown")
    archetype_confidence = profile.get("archetype_confidence", 0.0)
    dominant_pain_points = profile.get("dominant_pain_points") or []
    identity_constants = profile.get("identity_constants") or {}

    voice_summary = ""
    if voice:
        voice_summary = f"""
Creator Voice Fingerprint:
- Tone: {voice.get("tone", "N/A")}
- Vocabulary: {voice.get("vocabulary_level", "N/A")}
- Energy: {voice.get("energy", "N/A")}
- Signature phrases: {", ".join(voice.get("signature_phrases", [])) or "none identified"}
- Delivery style: {voice.get("delivery_style", "N/A")}
""".strip()

    identity_summary = ""
    if identity_constants:
        identity_summary = "Creator Identity Constants:\n" + "\n".join(
            f"- {k}: {v}" for k, v in identity_constants.items()
        )

    video_block = "\n\n".join(video_analyses) if video_analyses else "(no video analyses — only note provided)"

    user_message = f"""CREATOR ARCHETYPE: {archetype} (confidence: {archetype_confidence:.0%})
CREATOR DOMINANT PAIN POINTS: {", ".join(dominant_pain_points) if dominant_pain_points else "unknown"}

{identity_summary}

{voice_summary}

--- INSPIRATION VIDEO ANALYSES ---
{video_block}

--- USER INSPIRATION NOTE ---
{note.strip() if note.strip() else "(none)"}

---
Now write the compatibility digest: which angles and techniques from above fit this creator's
archetype and voice, and exactly how to adapt them for AshwaMag Gummies content.
Flag any techniques that would feel inauthentic for this creator and explain why."""

    try:
        response = await client.chat.completions.create(
            model=GPT_MODEL,
            messages=[
                {"role": "system", "content": DIGEST_SYSTEM},
                {"role": "user", "content": user_message},
            ],
            temperature=0.7,
            max_completion_tokens=600,
        )
        digest = response.choices[0].message.content.strip()
    except Exception as exc:
        emit("progress", {"stage": "INSP", "message": f"Digest generation failed: {exc}", "done": True})
        job["inspiration_digest"] = None
        return

    job["inspiration_digest"] = digest

    emit("inspiration_digest", {"digest": digest, "videos_analyzed": len(video_analyses)})
    emit("progress", {"stage": "INSP", "message": "Inspiration digest ready.", "done": True})
