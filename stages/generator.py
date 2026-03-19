"""Stage: Generator — GPT-5.4 × 3 brief generation + GPT-4o × 3 CQ scoring in parallel."""
import os
import asyncio
import json
import re
from typing import Callable, Optional

from openai import AsyncOpenAI
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from ashwamag_config import FORMULATION, CONTENT_STRATEGY_RULES, VALID_CLAIMS, BANNED_ANGLES, BANNED_PHRASES

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
client = AsyncOpenAI(api_key=OPENAI_API_KEY)

GPT_GEN_MODEL = "gpt-5.4"
GPT_SCORE_MODEL = "gpt-4o"

BRIEF_TYPES = {
    1: "gmv_max",
    2: "archetype_best",
    3: "creators_own",
}

BRIEF_TYPE_DESCRIPTIONS = {
    1: "GMV Max — top combo + top pain point for archetype group, fully library-grounded",
    2: "Archetype Best — second combo variation, archetype-aligned",
    3: "Creator's Own Best — creator's dominant pain point from their actual videos × best matching library combo",
}

OUTPUT_FORMAT_INSTRUCTIONS = """
OUTPUT FORMAT — return ONLY a single valid JSON object with these exact fields:
{
  "brief_num": <1|2|3>,
  "brief_type": "<gmv_max|archetype_best|creators_own>",
  "hook_text": "<exact first-3-second hook line — what the creator says or shows in the first 3 seconds>",
  "pain_point": "<pain point addressed>",
  "combo": "<hook_type × narrative_type>",
  "beats": [
    {
      "time": "<e.g. 0-3s>",
      "beat_num": <integer>,
      "action": "<what the creator does/says>",
      "text_overlay": "<on-screen text, or null if none>",
      "audio": "<background music/sound cue, or null>",
      "product_integration": <null | "first_appearance" | "on_screen" | "demo" | "verbal_only">
    }
  ],
  "total_duration": "<e.g. 60-65s>",
  "key_claims": ["<3-4 product claims used — must be from VALID CLAIMS only>"],
  "visual_proof_elements": ["<what transformation/proof visuals to include>"],
  "cta": "<exact CTA line the creator says at the end>",
  "why_this_works": "<2-3 sentence rationale grounded in library data and creator fit>",
  "adoption_pct": "<estimated % of creators in this archetype group who successfully execute this format, e.g. '68%'>"
}

CRITICAL: Return ONLY the JSON. No markdown fences, no explanation text before or after.
""".strip()

CQ_SCORE_PROMPT_TEMPLATE = """You are a TikTok content quality scorer for supplement brands.
Score this brief on 10 dimensions (0-100 each). Return ONLY valid JSON, no markdown fences.

BRIEF:
{brief_json}

Return this exact JSON structure with all scores filled in:
{{
  "hook": {{"score": 0, "hook_clarity": 0, "hook_relevance": 0, "hook_scroll_stop": 0, "hook_promise": 0, "hook_authenticity": 0}},
  "education": {{"score": 0, "education_accuracy": 0, "education_simplicity": 0, "education_credibility": 0, "education_engagement": 0}},
  "depth": {{"score": 0, "depth_completeness": 0, "depth_specificity": 0, "depth_insight": 0, "depth_originality": 0, "depth_nuance": 0}},
  "visual_variety": {{"score": 0, "visual_dynamism": 0, "visual_product_shots": 0, "visual_b_roll": 0, "visual_text_overlays": 0, "visual_pacing": 0, "visual_transformation": 0, "visual_proof": 0}},
  "cta": {{"score": 0, "cta_clarity": 0, "cta_urgency": 0, "cta_specificity": 0, "cta_placement": 0}},
  "urgency": {{"score": 0, "urgency_scarcity": 0, "urgency_fomo": 0, "urgency_social_proof": 0, "urgency_timing": 0}},
  "trust_architecture": {{"score": 0, "trust_credentials": 0, "trust_coa": 0, "trust_transparency": 0, "trust_reviews": 0, "trust_science": 0}},
  "pacing_rhythm": {{"score": 0, "pacing_beat_density": 0, "pacing_information": 0, "pacing_transitions": 0, "pacing_retention": 0, "pacing_momentum": 0}},
  "product_presentation": {{"score": 0, "product_natural_integration": 0, "product_visual_proof": 0, "product_differentiation": 0, "product_timing": 0, "product_beadlet_demo": 0, "product_compliance": 0}},
  "ease_of_execution": {{"score": 0, "ease_equipment": 0, "ease_editing": 0, "ease_creator_fit": 0, "ease_replicability": 0, "ease_time": 0, "ease_authenticity_fit": 0}},
  "cq_total": 0,
  "cq_grade": "C",
  "top_strengths": ["strength 1", "strength 2"],
  "top_gaps": ["gap 1", "gap 2"],
  "adoption_pct": 50
}}

Grade scale: 800+ = A, 700+ = B, 600+ = C+, 500+ = C, <500 = D
cq_total = sum of the 10 dimension "score" values (each 0-100, max total = 1000).
Return ONLY the JSON. No markdown, no explanation."""


def _build_system_prompt(brief_num: int, job: dict) -> str:
    """Assemble the full system prompt for a given brief number."""
    profile: dict = job.get("profile") or {}
    voice: dict = job.get("voice") or {}
    library_intel: Optional[dict] = job.get("library_intel")
    inspiration_digest: Optional[str] = job.get("inspiration_digest")
    library_selections: dict = job.get("library_selections") or {"brief_1": True, "brief_2": True, "brief_3": True}
    skip_library: bool = job.get("skip_library", False)

    brief_key = f"brief_{brief_num}"
    use_library = (
        not skip_library
        and library_selections.get(brief_key, True)
        and library_intel is not None
        and library_intel.get("available", False)
    )

    # 1. Role definition
    role = (
        "You are an elite TikTok content strategist for Root Labs. "
        "Your job is to create beat-by-beat content briefs for AshwaMag Gummies specifically. "
        "Every brief you write is for AshwaMag Gummies — this never changes."
    )

    # 2. AshwaMag product context
    product_context = f"PRODUCT CONTEXT:\n{FORMULATION}"

    # 3. Creator identity constants
    identity_constants = profile.get("identity_constants") or {}
    if identity_constants:
        identity_block = "CREATOR IDENTITY CONSTANTS:\n" + "\n".join(
            f"- {k}: {v}" for k, v in identity_constants.items()
        )
    else:
        archetype = profile.get("archetype", "unknown")
        dominant_pain_points = profile.get("dominant_pain_points") or []
        identity_block = (
            f"CREATOR IDENTITY:\n"
            f"- Archetype: {archetype}\n"
            f"- Dominant pain points in their content: {', '.join(dominant_pain_points) or 'unknown'}\n"
            f"- Archetype confidence: {profile.get('archetype_confidence', 0.0):.0%}"
        )

    # 4. Voice fingerprint
    if voice:
        voice_lines = []
        for key, label in [
            ("tone", "Tone"),
            ("vocabulary_level", "Vocabulary"),
            ("energy", "Energy"),
            ("delivery_style", "Delivery style"),
            ("pacing", "Pacing"),
            ("humor_style", "Humor style"),
        ]:
            val = voice.get(key)
            if val:
                voice_lines.append(f"- {label}: {val}")
        sig_phrases = voice.get("signature_phrases") or []
        if sig_phrases:
            voice_lines.append(f"- Signature phrases: {', '.join(sig_phrases)}")
        do_list = voice.get("do") or []
        dont_list = voice.get("dont") or []
        if do_list:
            voice_lines.append(f"- DO (voice rules): {', '.join(do_list)}")
        if dont_list:
            voice_lines.append(f"- DON'T (voice rules): {', '.join(dont_list)}")
        voice_block = "CREATOR VOICE FINGERPRINT:\n" + "\n".join(voice_lines)
    else:
        voice_block = "CREATOR VOICE FINGERPRINT: Not available — use archetype defaults."

    # 5. Library intelligence (if selected and available)
    if use_library:
        lib_context = library_intel["briefs"][brief_key].get("context_str", "")
        library_block = lib_context if lib_context else "LIBRARY INTELLIGENCE: Not available for this brief."
    else:
        library_block = "LIBRARY INTELLIGENCE: Not used for this brief."

    # 6. Inspiration digest
    if inspiration_digest:
        inspiration_block = f"INSPIRATION DIGEST (adapt these angles for this creator):\n{inspiration_digest}"
    else:
        inspiration_block = "INSPIRATION DIGEST: None provided."

    # 7. AshwaMag compliance rules
    banned_angles_list = ", ".join(sorted(BANNED_ANGLES))
    banned_phrases_list = "\n".join(f"  - \"{p}\"" for p in BANNED_PHRASES)
    valid_claims_list = "\n".join(f"  - {c}" for c in VALID_CLAIMS)
    compliance_block = f"""ASHWAMAG COMPLIANCE RULES — HARD LIMITS, NEVER VIOLATE:
BANNED ANGLES (never use these as hooks or narrative frames):
  {banned_angles_list}

BANNED PHRASES (never write these words/phrases):
{banned_phrases_list}

VALID CLAIMS ONLY — every product claim must come from this list:
{valid_claims_list}

Structure/function language ONLY. No disease claims. No medical treatment claims."""

    # 8. Content strategy rules
    strategy_block = CONTENT_STRATEGY_RULES.strip()

    # 9. Chain-of-thought instructions
    cot_block = """BEFORE WRITING THE BRIEF — think step by step:
1. What pain point hooks this creator's specific audience? (consider their archetype and dominant themes)
2. What hook technique fits their voice fingerprint? (match their energy, tone, vocabulary)
3. What are the exact first 3 seconds? (the scroll-stop moment — be very specific)
4. How does the product appear naturally without feeling forced? (choose a beat, make it organic)
5. What transformation proof closes the loop? (the 'before → after' or 'reason why it works' moment)
Only after thinking through all 5 steps, write the brief."""

    # 10. Output format
    output_block = OUTPUT_FORMAT_INSTRUCTIONS

    sections = [
        role,
        "",
        product_context,
        "",
        identity_block,
        "",
        voice_block,
        "",
        library_block,
        "",
        inspiration_block,
        "",
        compliance_block,
        "",
        strategy_block,
        "",
        cot_block,
        "",
        output_block,
    ]
    return "\n".join(sections)


def _build_user_prompt(brief_num: int, job: dict) -> str:
    """Build the user-turn prompt for brief generation."""
    strategy: str = job.get("strategy") or "balanced"
    intent: str = job.get("intent") or ""
    inspiration_note: str = job.get("inspiration_note") or ""
    feedback: str = job.get("regen_feedback") or ""
    profile: dict = job.get("profile") or {}

    brief_type = BRIEF_TYPES[brief_num]
    brief_desc = BRIEF_TYPE_DESCRIPTIONS[brief_num]

    dominant_pain_points = profile.get("dominant_pain_points") or []
    creator_pain = dominant_pain_points[0] if dominant_pain_points else "sleep"

    lines = [
        f"Generate BRIEF {brief_num}: {brief_type.upper()} — {brief_desc}",
        "",
        f"Strategy selection: {strategy}",
    ]

    if intent.strip():
        lines += ["", f"User strategy intent: {intent.strip()}"]

    if inspiration_note.strip():
        lines += ["", f"Inspiration note from user: {inspiration_note.strip()}"]

    if brief_num == 3:
        lines += [
            "",
            f"For Brief 3 (Creator's Own Best): ground this in the creator's dominant pain point "
            f"'{creator_pain}' — this came from their actual content, not the library.",
        ]

    if feedback.strip():
        lines += [
            "",
            f"REGENERATION FEEDBACK (previous version was rejected — fix these issues):",
            feedback.strip(),
        ]

    lines += [
        "",
        f"Return the complete beat-by-beat brief for AshwaMag Gummies as a single valid JSON object.",
    ]

    return "\n".join(lines)


def _parse_brief_json(raw: str, brief_num: int) -> dict:
    """Extract and parse JSON from GPT output, handling markdown fences."""
    text = raw.strip()
    # Strip markdown fences if present
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Attempt to find first { ... } block
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            data = json.loads(match.group())
        else:
            raise ValueError(f"Could not parse JSON from GPT output for brief {brief_num}")
    # Ensure brief_num is correct
    data["brief_num"] = brief_num
    if "brief_type" not in data:
        data["brief_type"] = BRIEF_TYPES[brief_num]
    return data


def _parse_cq_json(raw: str) -> dict:
    """Extract and parse CQ score JSON from GPT-4o output."""
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise ValueError("Could not parse CQ score JSON from GPT-4o output")


async def generate_brief(brief_num: int, job: dict, emit: Callable) -> dict:
    """Call GPT-5.4 to generate one brief. Returns the parsed brief dict."""
    emit("progress", {
        "stage": "GEN",
        "message": f"Generating Brief {brief_num} ({BRIEF_TYPES[brief_num]})...",
    })

    system_prompt = _build_system_prompt(brief_num, job)
    user_prompt = _build_user_prompt(brief_num, job)

    response = await client.chat.completions.create(
        model=GPT_GEN_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.8,
        max_completion_tokens=2500,
    )

    raw = response.choices[0].message.content or ""
    brief = _parse_brief_json(raw, brief_num)

    emit("progress", {
        "stage": "GEN",
        "message": f"Brief {brief_num} generated.",
        "brief_num": brief_num,
    })
    return brief


async def score_brief(brief_dict: dict) -> dict:
    """Call GPT-4o to CQ-score one brief. Returns the CQ score dict."""
    brief_json_str = json.dumps(brief_dict, indent=2)
    prompt = CQ_SCORE_PROMPT_TEMPLATE.format(brief_json=brief_json_str)

    response = await client.chat.completions.create(
        model=GPT_SCORE_MODEL,
        messages=[
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_completion_tokens=1200,
    )

    raw = response.choices[0].message.content or ""
    cq = _parse_cq_json(raw)

    # Ensure cq_total and grade are consistent
    dim_keys = [
        "hook", "education", "depth", "visual_variety", "cta",
        "urgency", "trust_architecture", "pacing_rhythm",
        "product_presentation", "ease_of_execution",
    ]
    computed_total = sum(
        cq.get(dim, {}).get("score", 0) if isinstance(cq.get(dim), dict) else 0
        for dim in dim_keys
    )
    cq["cq_total"] = computed_total

    # Assign grade
    if computed_total >= 800:
        cq["cq_grade"] = "A"
    elif computed_total >= 700:
        cq["cq_grade"] = "B"
    elif computed_total >= 600:
        cq["cq_grade"] = "C+"
    elif computed_total >= 500:
        cq["cq_grade"] = "C"
    else:
        cq["cq_grade"] = "D"

    return cq


async def run(job: dict, emit: Callable) -> None:
    """Orchestrate brief generation and CQ scoring.

    Normal flow: generate all 3 briefs in parallel, then score all 3 in parallel.
    Regen flow: if job["regen_brief_num"] is set, regenerate and re-score only that brief,
    preserving the other two in job["briefs"].
    """
    regen_num: Optional[int] = job.get("regen_brief_num")

    emit("progress", {"stage": "GEN", "message": "Starting brief generation..."})

    if regen_num is not None:
        # --- Regeneration of a single brief ---
        existing_briefs: list[dict] = job.get("briefs") or []
        brief_map = {b.get("brief_num"): b for b in existing_briefs}

        emit("progress", {
            "stage": "GEN",
            "message": f"Regenerating Brief {regen_num} ({BRIEF_TYPES.get(regen_num, '?')})...",
        })

        new_brief = await generate_brief(regen_num, job, emit)

        emit("progress", {
            "stage": "GEN",
            "message": f"Re-scoring Brief {regen_num}...",
        })
        cq = await score_brief(new_brief)
        new_brief["cq"] = cq

        # Replace only the regenerated brief
        brief_map[regen_num] = new_brief
        job["briefs"] = [brief_map.get(n, {}) for n in [1, 2, 3] if brief_map.get(n)]

        emit("brief_ready", {
            "brief_num": regen_num,
            "brief_type": new_brief.get("brief_type"),
            "hook_text": new_brief.get("hook_text"),
            "cq_total": cq.get("cq_total"),
            "cq_grade": cq.get("cq_grade"),
            "regenerated": True,
        })

    else:
        # --- Normal flow: generate all 3 in parallel ---
        gen_tasks = [
            generate_brief(1, job, emit),
            generate_brief(2, job, emit),
            generate_brief(3, job, emit),
        ]
        briefs_raw = await asyncio.gather(*gen_tasks, return_exceptions=True)

        # Handle any generation failures
        briefs: list[dict] = []
        for i, result in enumerate(briefs_raw, start=1):
            if isinstance(result, Exception):
                emit("progress", {
                    "stage": "GEN",
                    "message": f"Brief {i} generation failed: {result}",
                    "error": True,
                })
                # Insert a placeholder so scoring doesn't skip the slot
                briefs.append({"brief_num": i, "brief_type": BRIEF_TYPES[i], "error": str(result)})
            else:
                briefs.append(result)

        emit("progress", {
            "stage": "GEN",
            "message": "All 3 briefs generated. Starting CQ scoring...",
        })

        # Score all 3 in parallel (skip errored briefs)
        async def _safe_score(brief: dict) -> dict:
            if brief.get("error"):
                return {"cq_total": 0, "cq_grade": "D", "error": "brief generation failed"}
            return await score_brief(brief)

        score_results = await asyncio.gather(
            *[_safe_score(b) for b in briefs],
            return_exceptions=True,
        )

        # Merge CQ scores into briefs
        for i, (brief, cq_result) in enumerate(zip(briefs, score_results)):
            if isinstance(cq_result, Exception):
                brief["cq"] = {
                    "cq_total": 0,
                    "cq_grade": "D",
                    "error": f"Scoring failed: {cq_result}",
                }
                emit("progress", {
                    "stage": "GEN",
                    "message": f"Brief {i+1} scoring failed: {cq_result}",
                    "error": True,
                })
            else:
                brief["cq"] = cq_result
                emit("brief_ready", {
                    "brief_num": brief.get("brief_num", i + 1),
                    "brief_type": brief.get("brief_type"),
                    "hook_text": brief.get("hook_text"),
                    "cq_total": cq_result.get("cq_total"),
                    "cq_grade": cq_result.get("cq_grade"),
                })

        job["briefs"] = briefs

    emit("progress", {
        "stage": "GEN",
        "message": "Brief generation and scoring complete.",
        "done": True,
        "brief_count": len(job.get("briefs", [])),
    })
