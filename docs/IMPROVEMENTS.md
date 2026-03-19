# Approved Improvements — Implementation Plan

These 5 improvements are approved and prioritized. Implement in order.

---

## Improvement 1: Use Voice Examples in Brief Generation
**File**: `stages/generator.py` (`_build_system_prompt()`)
**Impact**: Highest — this is the single biggest quality gap

### What to change
Stage D produces `voice.example_hook_in_their_voice` and `voice.example_cta_in_their_voice`. Currently ignored in Stage E.

Inject them as hard structural constraints in the system prompt — not just informational context:

```python
# In _build_system_prompt(), voice section currently:
f"- Tone: {voice.get('tone')}\n- Vocabulary: {voice.get('vocabulary')}\n..."

# Change to include examples as constraints:
f"""CREATOR VOICE — YOU MUST MATCH THIS EXACTLY:
- Tone: {voice.get('tone')}
- Vocabulary: {voice.get('vocabulary')}
- Signature phrases (USE AT LEAST 2):
{chr(10).join(f'  * "{p}"' for p in voice.get('signature_phrases', []))}
- AVOID: {', '.join(voice.get('avoid', []))}

VOICE EXAMPLES — YOUR WRITING MUST SOUND LIKE THESE:
Hook example: "{voice.get('example_hook_in_their_voice', '')}"
CTA example: "{voice.get('example_cta_in_their_voice', '')}"

The brief's hook MUST match the style, energy, and vocabulary of the hook example above.
The brief's CTA MUST match the style of the CTA example above.
"""
```

Also add to output format: `"signature_phrases_used": ["phrase1", "phrase2"]` — forces the model to declare which phrases it used (accountability).

---

## Improvement 2: Beat Structure Enforcement
**File**: `stages/generator.py` (output format instructions + system prompt)
**Impact**: High — directly improves creator execution quality

### What to change
Current output format has unconstrained `beats[]`. Replace with typed, duration-bounded schema:

```python
OUTPUT_FORMAT_INSTRUCTIONS = """
...
"beats": [
  {
    "beat_num": 1,
    "beat_type": "hook",          // REQUIRED: hook|problem|solution|proof|cta
    "time_range": "0-5s",         // REQUIRED: must be within 55-65s total
    "action": "...",              // camera direction, props, movement — specific
    "script": "...",              // VERBATIM words, ~20-30 words per beat
    "text_overlay": "...",        // exact text or null
    "music": "...",               // sound cue or null
    "product_integration": null   // null | "first_appearance" | "on_screen" | "demo" | "verbal_only"
  }
],
"total_beats": 5,                 // REQUIRED: must be 4, 5, or 6
"estimated_duration": "60s",      // REQUIRED: must be 55-65s
```

Add to system prompt:
```
BEAT STRUCTURE RULES:
- Exactly 4, 5, or 6 beats (not fewer, not more)
- Required beat types: hook (4-6s), problem (8-12s), solution (10-15s), proof (8-12s), cta (5-8s)
- Each beat: ~20-30 words of script = ~4-6 seconds of speech
- Total video duration: 55-65 seconds
- Product MUST appear by beat 3 at latest
```

---

## Improvement 3: Archetype-Specific Generation Constraints
**File**: `stages/generator.py` (`_build_system_prompt()`)
**Impact**: High — briefs feel authentic to creator type

### What to change
Add an archetype routing block. Read from `job["profile"]["archetype"]` and inject type-specific constraints:

```python
ARCHETYPE_CONSTRAINTS = {
    "pharmacist": {
        "required": "Lead with clinical evidence or credentials. Use precise language. Explain the mechanism.",
        "hook_style": "skeptical_setup or authority_intro",
        "forbidden_hooks": ["relatable_callout without credential grounding"],
        "cta_style": "Professional, links to personal credibility. 'As a pharmacist...' or similar.",
    },
    "wellness_lifestyle": {
        "required": "Lead with personal story or transformation. Emphasize experiential authenticity.",
        "hook_style": "relatable_callout or personal_story",
        "forbidden_hooks": ["authority_intro without personal stake"],
        "cta_style": "Conversational, feels organic. Never pushy or salesy.",
    },
    "fitness": {
        "required": "Lead with performance metric or physical result. High energy. Emphasize results.",
        "hook_style": "transformation or challenge",
        "forbidden_hooks": ["slow narrative openers"],
        "cta_style": "Direct, action-oriented. Fast.",
    },
    "direct_commerce": {
        "required": "Lead with value or deal framing. Emphasize ROI or comparison.",
        "hook_style": "comparison or value_reveal",
        "forbidden_hooks": ["authority_intro", "slow personal story"],
        "cta_style": "Urgent, specific, deal-focused.",
    },
    # Add more archetypes as encountered
}
```

Inject the matching constraint block into the system prompt for each brief.

---

## Improvement 4: Post-Generation Validation Checklist
**File**: `stages/generator.py` (add validation prompt step after generation)
**Impact**: Medium — compliance guarantee; prevents broken briefs reaching users

### What to change
After each brief is generated (before CQ scoring), run a lightweight validation. Two approaches:

**Option A (preferred — no extra LLM call)**: Add validation checklist to the generation system prompt as a final instruction:

```
BEFORE RETURNING YOUR JSON, verify:
✓ All claims are from VALID_CLAIMS (no disease treatment, no weight claims)
✓ No BANNED_PHRASES present
✓ No BANNED_ANGLES (anxiety, weight_body_comp)
✓ Total duration 55-65s
✓ At least 1 transformation_proof or social_proof element in the beats
✓ CTA is specific (not just "link in bio") and matches creator CTA style
✓ At least 2 signature phrases from the voice profile used naturally
✓ Hook matches the voice example provided above

If any check fails, revise the relevant beat before returning.
Add a "validation_passed": true field to confirm you checked.
```

**Option B**: Separate lightweight GPT-4o-mini validation call after generation — checks only the 8 rules above, returns pass/fail + flagged items, regenerates if failed.

Start with Option A (no latency overhead). If compliance issues persist, upgrade to Option B.

---

## Improvement 5: Enrich Library Context with Rationale
**File**: `stages/library.py` + `ashwamag_config.py`
**Impact**: Medium — better informed brief generation

### What to change
Current library output:
```python
{"pain_point": "sleep", "combo": "relatable_callout × problem_solution", "pain_gmv": 593000, "combo_gmv": 580000}
```

Expand to include "why this works" and what proof elements to include:

In `ashwamag_config.py`, add `LIBRARY_RATIONALE` dict:
```python
LIBRARY_RATIONALE = {
    "sleep": {
        "why_it_converts": "Immediate relatable pain — 'brain won't shut off at 2AM' hits hard. High purchase urgency.",
        "proof_elements": ["mood tracker screenshot", "before/after energy comparison", "beadlet close-up"],
        "anti_patterns": ["generic better sleep claim without personal stake", "medical claims about insomnia"],
    },
    "stress": {
        "why_it_converts": "Ashwagandha is increasingly known; naming KSM-66 builds credibility fast.",
        "proof_elements": ["side-by-side stressed vs calm", "cortisol reference (careful — no direct claim)", "lifestyle proof"],
        "anti_patterns": ["anxiety treatment framing", "cortisol face/belly language"],
    },
    ...
}

COMBO_RATIONALE = {
    "relatable_callout × problem_solution": {
        "why": "Opens with shared struggle → names mechanism → shows resolution. Highest trust arc.",
        "who_it_works_for": ["wellness_lifestyle", "pharmacist", "authentic_testimonial"],
        "what_not_to_do": "Don't skip the problem — jumping straight to solution feels like an ad",
    },
    ...
}
```

Inject into Stage E system prompt as structured context.

---

## Implementation Order

1. **Improvement 1** (voice examples) — fastest win, single function change
2. **Improvement 2** (beat structure) — update output format + system prompt
3. **Improvement 3** (archetype constraints) — add routing dict + inject per brief
4. **Improvement 4** (validation checklist) — add to system prompt
5. **Improvement 5** (library rationale) — add to config + library.py injection

After each improvement: run `test_5creators.py` to verify no regression in field scores, CQ, and timing.
