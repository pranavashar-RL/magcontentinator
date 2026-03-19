"""Stage: Generator — GPT-5.4 × 3 brief generation + GPT-4o × 3 CQ scoring in parallel."""
import os
import asyncio
import json
import re
from typing import Callable, Optional

from openai import AsyncOpenAI
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from ashwamag_config import (
    FORMULATION, CONTENT_STRATEGY_RULES, VALID_CLAIMS, BANNED_ANGLES, BANNED_PHRASES,
    ARCHETYPE_GROUPS, get_archetype_group,
)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
client = AsyncOpenAI(api_key=OPENAI_API_KEY)

GPT_GEN_MODEL = "gpt-5.4"
GPT_SCORE_MODEL = "gpt-4o"

ARCHETYPE_CONSTRAINTS = {
    "medical_authority": {
        "required": "Lead with clinical evidence, credentials, or mechanism explanation. Use precise medical/pharmacological language. Establish expertise in first 3 seconds.",
        "hook_styles": "controversial_take, bold_claim, or authority_intro — never pure relatable_callout without credential grounding",
        "forbidden": "Vague wellness language without mechanism. 'This supplement changed my life' framing.",
        "cta_style": "Professional, links to personal credibility. 'As a pharmacist/nurse/doctor, this is what I'd recommend...' or similar.",
    },
    "wellness_lifestyle": {
        "required": "Lead with personal story, transformation, or relatable shared struggle. Emphasize experiential authenticity. Make it feel like a recommendation from a trusted friend.",
        "hook_styles": "relatable_callout, personal_story, or before_after",
        "forbidden": "authority_intro without personal stake. Clinical language without warmth. Hard sell framing.",
        "cta_style": "Conversational, feels organic and genuine. Never pushy or corporate.",
    },
    "fitness": {
        "required": "Lead with performance metric, physical result, or athletic context. High energy, fast pace. Emphasize tangible results.",
        "hook_styles": "bold_claim, before_after, or relatable_callout with performance framing",
        "forbidden": "Slow narrative openers. Wellness/lifestyle language without performance angle.",
        "cta_style": "Direct, action-oriented, fast. Performance or recovery angle on the CTA.",
    },
    "direct_commerce": {
        "required": "Lead with value, comparison, or deal framing. Show product visually early. Emphasize ROI vs alternatives.",
        "hook_styles": "comparison, relatable_callout, or social_proof_callout",
        "forbidden": "Slow authority_intro. Long narrative without product. Abstract wellness claims.",
        "cta_style": "Urgent, specific, deal-focused. Include price anchor or comparison.",
    },
    "ugc_authentic": {
        "required": "Authentic personal testimony. Unscripted energy. Own experience must be central, not general claims.",
        "hook_styles": "personal_story, relatable_callout, or before_after",
        "forbidden": "Expert positioning without credential. Corporate or scripted tone.",
        "cta_style": "Genuine personal recommendation. 'I literally just ordered another...' style.",
    },
    "blue_collar_rural": {
        "required": "Grounded, practical, working-person context. Energy depletion and recovery angle strongest. No wellness-speak.",
        "hook_styles": "relatable_callout, personal_story, or bold_claim with work context",
        "forbidden": "Wellness lifestyle framing. Aspirational tone. Anything that feels luxury or premium.",
        "cta_style": "Simple, direct, value-focused. Time-pressed worker who needs to get back to work.",
    },
    "reaction_story": {
        "required": "Reaction or narrative format. Story arc must be clear and engaging. Humor or surprise acceptable.",
        "hook_styles": "relatable_callout, personal_story, or negative_framing",
        "forbidden": "Dry educational format. Pure product demo without story.",
        "cta_style": "Conversational story close. Natural segue from narrative to recommendation.",
    },
}

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
  "hook_text": "<exact first-3-second hook line — verbatim words the creator says>",
  "hook_visual": "<exact shot description for the opening frame — setting, framing, props, body language, text overlay>",
  "pain_point": "<pain point addressed>",
  "combo": "<hook_type × narrative_type>",
  "beats": [
    {
      "beat_num": <integer starting at 1>,
      "beat_type": "<REQUIRED: hook|problem|solution|proof|cta>",
      "time_range": "<e.g. 0-5s — must sum to 55-65s total>",
      "action": "<precise camera direction and physical action — what creator does, how they move, shot type, any props used, jump cuts>",
      "script": "<VERBATIM words the creator speaks in this beat — full sentences, their exact voice, nothing paraphrased, ~20-30 words>",
      "text_overlay": "<exact on-screen text including any emoji, capitalization style — or null>",
      "music": "<background music/sound cue or transition sound — or null>",
      "product_integration": <null | "first_appearance" | "on_screen" | "demo" | "verbal_only">
    }
  ],
  "total_beats": <REQUIRED integer: 4, 5, or 6>,
  "estimated_duration": "<REQUIRED: must be 55-65s, e.g. '60s'>",
  "full_script": "<the complete verbatim script end to end — every word the creator says from hook to CTA, as one block of text>",
  "narrative_flow": "<2-3 sentence summary of the complete narrative arc — how it opens, builds, and closes>",
  "total_duration": "<e.g. 60-65s>",
  "key_claims": ["<3-4 product claims used — must be from VALID CLAIMS only>"],
  "visual_proof_elements": ["<specific proof visuals — beadlet close-up, COA PIP, review screenshot, comparison graphic, etc>"],
  "cta": "<exact verbatim CTA line the creator says at the end>",
  "production_notes": "<1 paragraph of practical production direction: where to film, what to wear, exact props needed, camera setup, editing style, text overlay style — everything a creator needs to shoot this without asking a single question>",
  "why_this_works": "<2-3 sentence rationale grounded in library GMV data and creator fit — name the combo, name the data>",
  "adoption_pct": "<estimated % of creators in this archetype group who can execute this format>",
  "signature_phrases_used": ["<phrase 1 from voice profile used in script>", "<phrase 2 from voice profile used in script>"],
  "validation_passed": <true — required: confirms compliance checklist was run>
}

CRITICAL RULES FOR SCRIPT WRITING:
- Every "script" field must be VERBATIM — write exactly what they say, in their voice, using their signature phrases
- The "full_script" field must be a complete readable script from first word to last
- Do NOT write "[Creator explains X]" — write the actual words they would say
- Match the creator's vocabulary, energy, pacing, and signature phrases exactly
- CRITICAL: Return ONLY the JSON. No markdown fences, no explanation text before or after.
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

    # 4. Voice fingerprint (Improvement 1: fix field key mismatches + inject examples as hard constraints)
    if voice:
        voice_lines = []
        for key, label in [
            ("tone", "Tone"),
            ("vocabulary_level", "Vocabulary"),
            ("speaking_pace", "Pacing"),          # was "pacing" — FIXED
            ("hook_style", "Hook style"),          # was missing — ADDED
            ("cta_style", "CTA style"),            # was missing — ADDED
            ("educational_style", "Educational style"),  # was missing — ADDED
        ]:
            val = voice.get(key)
            if val:
                voice_lines.append(f"- {label}: {val}")

        sig_phrases = voice.get("signature_phrases") or []
        if sig_phrases:
            phrases_formatted = "\n".join(f'  * "{p}"' for p in sig_phrases)
            voice_lines.append(
                f"- Signature phrases (YOU MUST USE AT LEAST 2 OF THESE IN THE SCRIPT):\n{phrases_formatted}"
            )

        avoid_list = voice.get("avoid") or []   # was "dont" — FIXED
        if avoid_list:
            voice_lines.append(f"- AVOID these voice patterns: {', '.join(avoid_list)}")

        auth_markers = voice.get("authenticity_markers") or []  # was missing — ADDED
        if auth_markers:
            voice_lines.append(f"- Authenticity markers (what makes them sound real): {', '.join(auth_markers)}")

        voice_block = "CREATOR VOICE — YOU MUST MATCH THIS EXACTLY:\n" + "\n".join(voice_lines)

        # Voice examples as hard structural constraints
        example_hook = voice.get("example_hook_in_their_voice", "")
        example_cta = voice.get("example_cta_in_their_voice", "")
        if example_hook or example_cta:
            voice_block += "\n\nVOICE EXAMPLES — YOUR WRITING MUST SOUND LIKE THESE:"
            if example_hook:
                voice_block += f'\nHook example (match this style, energy, vocabulary): "{example_hook}"'
                voice_block += "\nThe brief's hook MUST match the style of the hook example above."
            if example_cta:
                voice_block += f'\nCTA example (match this style): "{example_cta}"'
                voice_block += "\nThe brief's CTA MUST match the style of the CTA example above."
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

    # 5b. Archetype-specific constraints (Improvement 3)
    archetype = profile.get("archetype", "everyday_consumer")
    archetype_group = get_archetype_group(archetype)
    constraints = ARCHETYPE_CONSTRAINTS.get(archetype_group, ARCHETYPE_CONSTRAINTS["ugc_authentic"])
    archetype_block = (
        f"ARCHETYPE CONSTRAINTS FOR THIS CREATOR ({archetype} / group: {archetype_group}):\n"
        f"- Required approach: {constraints['required']}\n"
        f"- Hook styles that work: {constraints['hook_styles']}\n"
        f"- FORBIDDEN: {constraints['forbidden']}\n"
        f"- CTA style: {constraints['cta_style']}"
    )

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

    # 7b. Beat structure rules (Improvement 2)
    beat_structure_block = """BEAT STRUCTURE RULES — REQUIRED:
- total_beats MUST be 4, 5, or 6. Never fewer than 4, never more than 6.
- Beat order: hook → [problem] → solution → [proof] → cta
  * hook (REQUIRED): 4-6s — the scroll-stop opening moment
  * problem (optional): 8-12s — the pain point addressed
  * solution (REQUIRED): 10-15s — how AshwaMag addresses it
  * proof (REQUIRED): 8-12s — transformation evidence, COA, beadlet demo, or social proof
  * cta (REQUIRED): 5-8s — specific call to action with urgency
- Each beat script: ~20-30 words = ~4-6 seconds of speech
- Total video: 55-65 seconds — never shorter, never longer
- Product MUST appear by beat 3 (solution beat) at latest
- product_integration type: use "first_appearance" only once per brief"""

    # 8. Content strategy rules
    strategy_block = CONTENT_STRATEGY_RULES.strip()

    # 9. Chain-of-thought + validation checklist (Improvements 4)
    cot_block = """BEFORE WRITING THE BRIEF — think step by step:
1. What pain point hooks this creator's specific audience? (consider their archetype and dominant themes)
2. What hook technique fits their voice fingerprint? (match their energy, tone, vocabulary)
3. What are the exact first 3 seconds? (the scroll-stop moment — be very specific)
4. How does the product appear naturally without feeling forced? (choose a beat, make it organic)
5. What transformation proof closes the loop? (the 'before → after' or 'reason why it works' moment)
Only after thinking through all 5 steps, write the brief.

BEFORE RETURNING YOUR JSON — run this validation checklist:
✓ All claims are from VALID_CLAIMS only (no disease treatment, no weight claims, no medical diagnosis)
✓ No BANNED_PHRASES appear anywhere in the script
✓ No BANNED_ANGLES used as hooks or narrative frames
✓ Total estimated duration is 55-65s
✓ At least 1 proof element (transformation, COA, beadlet demo, social proof) in the beats
✓ CTA is specific (not just "link in bio") and matches creator's CTA style
✓ At least 2 signature phrases from the voice profile used naturally in the script
✓ Hook matches the style of the voice example provided above (if examples were provided)

If any check fails, revise the relevant beat or section before returning.
Add "validation_passed": true to your JSON to confirm you completed this check."""

    # 10. Output format
    output_block = OUTPUT_FORMAT_INSTRUCTIONS

    sections = [
        role,
        "",
        product_context,
        "",
        identity_block,
        "",
        archetype_block,
        "",
        voice_block,
        "",
        library_block,
        "",
        inspiration_block,
        "",
        compliance_block,
        "",
        beat_structure_block,
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
    # Beat truncation fallback: if model produced > 6 beats, trim to 6
    beats = data.get("beats", [])
    if len(beats) > 6:
        data["beats"] = beats[:6]
        data["total_beats"] = len(data["beats"])
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
        max_completion_tokens=5000,
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
