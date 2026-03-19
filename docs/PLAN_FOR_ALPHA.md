# ALPHA Phase 2 + Phase 3 — End-to-End Implementation Plan

> This document is written FOR ALPHA to execute Phase 2 (implement 5 improvements) and Phase 3 (deploy + benchmark).
> Read this BEFORE writing any code. Phase 1 review is in `docs/REVIEW_BY_ALPHA.md`.

---

## Pre-Flight Checklist

Before writing any code:
1. Verify local server is running: `lsof -i :8000 || uvicorn main:app --reload --port 8000`
2. Verify .env has OPENAI_API_KEY, APIFY_API_TOKEN, VIDEO_ANALYZER_URL, VIDEO_ANALYZER_KEY
3. Run baseline to confirm numbers: `python3 test_5creators.py http://localhost:8000`
   - Expected: 5/5 PASS, Avg CQ 815, All fields 5/5
4. If baseline doesn't match, stop and investigate before implementing

---

## Key Architecture Facts (from Phase 1 review)

- Working directory: `/Users/mosaic/Downloads/magcontentinator_webapp/`
- The ONLY file you'll modify for all 5 improvements: `stages/generator.py` (+ `ashwamag_config.py` for Imp 5)
- `stages/library.py` also needs a small change for Imp 5 (inject rationale into context_str)
- Do NOT touch: scraper.py, analyzer.py, profiler.py, voice.py, pipeline.py, main.py, index.html

**CRITICAL BUG to fix in Improvement 1** (previous review missed this):

Voice stage (`stages/voice.py`) produces these keys:
```
tone, vocabulary_level, signature_phrases, speaking_pace, hook_style,
cta_style, educational_style, authenticity_markers, avoid,
example_hook_in_their_voice, example_cta_in_their_voice
```

Generator currently reads `pacing` (should be `speaking_pace`), `dont` (should be `avoid`), `energy`, `delivery_style`, `humor_style` (none exist in voice schema). Fix these key mismatches as PART of Improvement 1.

---

## Improvement 1: Voice Examples + Fix Voice Field Mapping

**File**: `stages/generator.py` — only `_build_system_prompt()` function

**What to change** (replace the entire voice_block section, lines 143–168):

```python
# Old code reads wrong keys: pacing, dont, energy, delivery_style, humor_style
# New code: fix all key mismatches + add examples as hard constraints

if voice:
    voice_lines = []
    for key, label in [
        ("tone", "Tone"),
        ("vocabulary_level", "Vocabulary"),
        ("speaking_pace", "Pacing"),        # was "pacing" — FIXED
        ("hook_style", "Hook style"),        # was missing — ADDED
        ("cta_style", "CTA style"),          # was missing — ADDED
        ("educational_style", "Educational style"),  # was missing — ADDED
    ]:
        val = voice.get(key)
        if val:
            voice_lines.append(f"- {label}: {val}")

    sig_phrases = voice.get("signature_phrases") or []
    if sig_phrases:
        phrases_formatted = chr(10).join(f'  * "{p}"' for p in sig_phrases)
        voice_lines.append(f"- Signature phrases (YOU MUST USE AT LEAST 2 OF THESE IN THE SCRIPT):\n{phrases_formatted}")

    avoid_list = voice.get("avoid") or []   # was "dont" — FIXED
    if avoid_list:
        voice_lines.append(f"- AVOID these voice patterns: {', '.join(avoid_list)}")

    auth_markers = voice.get("authenticity_markers") or []  # was missing — ADDED
    if auth_markers:
        voice_lines.append(f"- Authenticity markers (what makes them sound real): {', '.join(auth_markers)}")

    # Voice examples as hard structural constraints
    example_hook = voice.get("example_hook_in_their_voice", "")
    example_cta = voice.get("example_cta_in_their_voice", "")

    voice_block = "CREATOR VOICE — YOU MUST MATCH THIS EXACTLY:\n" + "\n".join(voice_lines)

    if example_hook or example_cta:
        voice_block += "\n\nVOICE EXAMPLES — YOUR WRITING MUST SOUND LIKE THESE:"
        if example_hook:
            voice_block += f'\nHook example (match this style, energy, vocabulary): "{example_hook}"'
            voice_block += "\nThe brief\'s hook MUST match the style of the hook example above."
        if example_cta:
            voice_block += f'\nCTA example (match this style): "{example_cta}"'
            voice_block += "\nThe brief\'s CTA MUST match the style of the CTA example above."
else:
    voice_block = "CREATOR VOICE FINGERPRINT: Not available — use archetype defaults."
```

**Also update OUTPUT_FORMAT_INSTRUCTIONS** — add `signature_phrases_used` field after `adoption_pct`:
```python
"signature_phrases_used": ["<phrase 1 from voice profile>", "<phrase 2 from voice profile>"]
```

**Test after Improvement 1:**
```bash
python3 test_5creators.py http://localhost:8000
```
- CQ should increase (likely +15-25 points avg based on unlocking 8 voice fields)
- All briefs should include `signature_phrases_used` with ≥2 entries
- Field completeness must stay 5/5
- Kill criterion: if CQ < 770 avg, revert and investigate

---

## Improvement 2: Beat Structure Enforcement

**File**: `stages/generator.py` — two changes: OUTPUT_FORMAT_INSTRUCTIONS + `_build_system_prompt()` CoT section

**Change 1**: Replace the `beats` section in `OUTPUT_FORMAT_INSTRUCTIONS`:

```python
  "beats": [
    {
      "beat_num": <integer starting at 1>,
      "beat_type": "<REQUIRED: hook|problem|solution|proof|cta>",
      "time_range": "<e.g. 0-5s — must sum to 55-65s total>",
      "action": "<camera direction, props, movement — specific and executable>",
      "script": "<VERBATIM words the creator speaks — full sentences in their exact voice, ~20-30 words>",
      "text_overlay": "<exact on-screen text including emoji, capitalization — or null>",
      "music": "<background music/sound cue or null>",
      "product_integration": <null | "first_appearance" | "on_screen" | "demo" | "verbal_only">
    }
  ],
  "total_beats": <REQUIRED integer: 4, 5, or 6>,
  "estimated_duration": "<REQUIRED: must be 55-65s, e.g. '60s'>",
```

**Change 2**: Add beat structure rules to system prompt — insert after the compliance block and before CONTENT_STRATEGY_RULES. Add a new section:

```python
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
```

Insert this section in `_build_system_prompt()` sections list, after compliance_block:
```python
sections = [
    role, "", product_context, "", identity_block, "", voice_block, "",
    library_block, "", inspiration_block, "", compliance_block, "",
    beat_structure_block, "",   # NEW
    strategy_block, "", cot_block, "", output_block,
]
```

**Also add truncation fallback in `_parse_brief_json()`** — after parsing, if beats count > 6, trim to 6 with a log warning. Don't crash:
```python
beats = data.get("beats", [])
if len(beats) > 6:
    data["beats"] = beats[:6]
    data["total_beats"] = len(data["beats"])
```

**Test after Improvement 2:**
- All briefs must have 4-6 beats
- All briefs must have `total_beats` and `estimated_duration` fields
- Field completeness must stay 5/5
- CQ should stay ≥ improvement 1 baseline

---

## Improvement 3: Archetype-Specific Constraints

**File**: `stages/generator.py` — add ARCHETYPE_CONSTRAINTS dict at module level + inject in `_build_system_prompt()`

**Add at module level** (after imports, before BRIEF_TYPES):

```python
from ashwamag_config import ARCHETYPE_GROUPS, get_archetype_group

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
```

**In `_build_system_prompt()`**, add archetype constraint block:
```python
# After identity_block assembly, add:
archetype = profile.get("archetype", "everyday_consumer")
archetype_group = get_archetype_group(archetype)
constraints = ARCHETYPE_CONSTRAINTS.get(archetype_group, ARCHETYPE_CONSTRAINTS["ugc_authentic"])
archetype_block = f"""ARCHETYPE CONSTRAINTS FOR THIS CREATOR ({archetype} / group: {archetype_group}):
- Required approach: {constraints['required']}
- Hook styles that work: {constraints['hook_styles']}
- FORBIDDEN: {constraints['forbidden']}
- CTA style: {constraints['cta_style']}"""
```

Add `archetype_block` to sections list, after `identity_block`:
```python
sections = [
    role, "", product_context, "", identity_block, "",
    archetype_block, "",   # NEW — after identity
    voice_block, "", library_block, "", inspiration_block, "",
    compliance_block, "", beat_structure_block, "",
    strategy_block, "", cot_block, "", output_block,
]
```

**Test after Improvement 3:**
- Check that `rphreviews` brief hooks sound like authority_intro or controversial_take (medical_authority)
- Check that `bribez1` brief hooks sound relatable (wellness or ugc archetype)
- CQ should increase (likely +5-15 points on hook/ease_of_execution dimensions)

---

## Improvement 4: Post-Generation Validation Checklist

**File**: `stages/generator.py` — add validation instructions to `_build_system_prompt()` chain-of-thought section

**Replace the `cot_block`** entirely:

```python
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
```

**Also update OUTPUT_FORMAT_INSTRUCTIONS** — add `validation_passed` field after `signature_phrases_used`:
```python
"validation_passed": <true — required: confirms compliance checklist was run>
```

**Test after Improvement 4:**
- All briefs must include `validation_passed: true`
- Spot-check: do any briefs include banned phrases? They should not.
- CQ compliance dimension score should improve

---

## Improvement 5: Library Rationale

**Files**: `ashwamag_config.py` + `stages/library.py`

### Step A: Add to `ashwamag_config.py`

Add these two dicts after the existing `CONTENT_STRATEGY_RULES`:

```python
LIBRARY_RATIONALE = {
    "sleep": {
        "why_it_converts": "Immediate relatable pain — 'brain won't shut off at 2AM' is universal. High purchase urgency because the pain is felt nightly. $593K GMV across 58 videos confirms this is the #1 AshwaMag pain point.",
        "proof_elements_that_work": ["sleep tracker screenshot showing improvement", "beadlet close-up (visual proof of delivery)", "COA/lab results as PIP insert"],
        "anti_patterns": ["generic 'better sleep' claim without personal stake", "clinical insomnia treatment framing", "cortisol face/belly language"],
    },
    "brain_fog": {
        "why_it_converts": "Brain fog has the highest avg GMV per video ($17,887) despite fewer videos — the audience is highly purchase-motivated. Credibility claim + mechanism explanation converts best.",
        "proof_elements_that_work": ["focus/productivity comparison", "ingredient label close-up", "beadlet demonstration showing delivery"],
        "anti_patterns": ["vague 'sharpen your mind' language without mechanism", "disease-adjacent cognitive claims"],
    },
    "stress_cortisol": {
        "why_it_converts": "KSM-66 ashwagandha has growing consumer recognition — naming it builds instant credibility. Large GMV volume ($268K) across 67 videos shows breadth of appeal.",
        "proof_elements_that_work": ["mood journal or tracker comparison", "COA showing KSM-66 standardization", "before/after lifestyle visual"],
        "anti_patterns": ["cortisol face/belly imagery (BANNED)", "stress = weight gain framing (BANNED)", "direct cortisol reduction claim (makes it a drug claim)", "anxiety treatment language"],
    },
    "low_energy": {
        "why_it_converts": "Blue-collar and working-parent audience — practical energy framing over wellness language. 2PM crash is the specific hook that resonates.",
        "proof_elements_that_work": ["day-in-the-life context showing demanding schedule", "energy level comparison", "no caffeine needed contrast"],
        "anti_patterns": ["aspirational wellness framing — this audience rejects it", "luxury product positioning"],
    },
    "muscle_recovery": {
        "why_it_converts": "Fitness audience is supplement-savvy — naming specific forms (malate, taurate) signals quality. Cramp relief has immediate emotional resonance.",
        "proof_elements_that_work": ["workout context video", "specific form label close-up", "cramp reenactment or anecdote"],
        "anti_patterns": ["generic 'muscle support' without naming specific forms", "body composition angle (BANNED)"],
    },
    "pms_hormones": {
        "why_it_converts": "High emotional stakes, monthly urgency, female-specific audience. Validation + practical solution framing converts better than clinical language.",
        "proof_elements_that_work": ["period tracking app screenshot", "relatable monthly struggle reenactment", "consumption ritual (showing daily habit)"],
        "anti_patterns": ["hormonal imbalance treatment claims (BANNED)", "disease-adjacent framing"],
    },
    "general_wellness": {
        "why_it_converts": "Lowest avg GMV ($2,833) — this pain point needs a strong differentiator to convert. Beadlet technology as proof of quality is the strongest angle.",
        "proof_elements_that_work": ["beadlet close-up as main visual", "ingredient comparison vs single-form competitors", "COA/lab certification callout"],
        "anti_patterns": ["generic supplement content — needs specific differentiator to stand out"],
    },
}

COMBO_RATIONALE = {
    "relatable_callout × problem_solution": {
        "why": "Opens with shared struggle the viewer instantly recognizes → names the mechanism → shows resolution. Highest trust arc. $580K GMV across 112 videos is the dominant proof.",
        "who_it_works_for": ["wellness_lifestyle", "ugc_authentic", "direct_commerce", "blue_collar_rural", "reaction_story"],
        "execution_note": "The relatable callout must be specific (not 'can't sleep' but 'lying awake at 2AM running through tomorrow's to-do list'). Generic callouts underperform.",
        "what_not_to_do": "Don't skip the problem beat — jumping straight to solution feels like an ad. The shared struggle is what earns the right to recommend.",
    },
    "bold_claim × problem_solution": {
        "why": "Authority assertion that demands attention. $118K GMV across 24 videos — strong avg GMV/video. Works best when the claim is specific and defensible.",
        "who_it_works_for": ["medical_authority", "fitness", "direct_commerce"],
        "execution_note": "Bold claim must be grounded immediately (within the same sentence or the next beat) — floating claims invite skepticism.",
        "what_not_to_do": "Don't use bold_claim without supporting credential or data. Unsupported bold claims feel like ads.",
    },
    "controversial_take × problem_solution": {
        "why": "Highest avg GMV per video ($19,219 across 6 videos) — the most selective but most powerful combo. Requires genuine expert credibility to execute.",
        "who_it_works_for": ["medical_authority"],
        "execution_note": "The controversial take must be defensible and specific (e.g., 'Most sleep supplements you're buying are basically useless magnesium oxide'). Vague controversy doesn't convert.",
        "what_not_to_do": "Don't attempt controversial_take with non-expert creators — it backfires without credential backing.",
    },
    "before_after × problem_solution": {
        "why": "$126K GMV across 9 videos — transformation proof drives high conversion. Visual proof (tracker, photos, comparison) is essential.",
        "who_it_works_for": ["wellness_lifestyle", "fitness", "ugc_authentic"],
        "execution_note": "The transformation must be specific and attributable to consistent use, not a single dose. Timeline matters (e.g., 'after 3 weeks').",
        "what_not_to_do": "Don't imply instant or dramatic transformation — sets unrealistic expectations and risks compliance issues.",
    },
    "personal_story × testimonial": {
        "why": "$39K GMV but consistent avg — authenticity arc where creator's personal experience becomes the social proof. Strongest for UGC/authentic archetypes.",
        "who_it_works_for": ["ugc_authentic", "wellness_lifestyle", "reaction_story"],
        "execution_note": "The story must have a specific moment ('the first morning I didn't hit snooze in months') — vague testimonials underperform.",
        "what_not_to_do": "Don't use personal_story framing with direct_commerce or medical_authority archetypes — it undermines their brand.",
    },
}
```

### Step B: Update `stages/library.py` to inject rationale

In `build_library_context()` in `ashwamag_config.py` (or in `library.py`'s `context_str` assembly), add rationale after the existing content.

Actually, `build_library_context()` is in `ashwamag_config.py`. Update it to include rationale:

```python
def build_library_context(archetype: str, brief_num: int = 1) -> str:
    """Build a library context string for injection into system prompts."""
    intel = get_library_intel(archetype, brief_num)
    pain = intel["pain_point_data"]
    pain_key = intel["pain_point"]
    combo = intel["combo"]

    # Get rationale (new)
    pain_rationale = LIBRARY_RATIONALE.get(pain_key, {})
    combo_rationale = COMBO_RATIONALE.get(combo, {})

    base = f"""LIBRARY INTELLIGENCE (from $1.73M GMV validated dataset):

BRIEF {brief_num} ASSIGNMENT:
- Pain Point: {intel["pain_point"].replace("_", " ").title()} (${intel["pain_total_gmv"]:,} total GMV, {pain["n_videos"]} videos, ${intel["pain_avg_gmv"]:,} avg)
- Combo: {intel["combo"]} (${intel["combo_gmv"]:,} total GMV)
- Archetype Group: {intel["archetype_group"].replace("_", " ").title()}

KEY INGREDIENTS FOR THIS PAIN POINT:
{chr(10).join(f"- {ing}" for ing in pain["key_ingredients"])}

PROVEN CLAIMS:
{chr(10).join(f"- {claim}" for claim in pain["claims"])}

HOOKS THAT CONVERT:
{chr(10).join(f"- {hook}" for hook in pain["hooks_that_convert"])}

VISUAL PROOF ELEMENTS (use at least one):
{chr(10).join(f"- {v}" for v in pain["visual_proof"])}"""

    # Add rationale if available
    if pain_rationale:
        base += f"\n\nWHY THIS PAIN POINT CONVERTS: {pain_rationale.get('why_it_converts', '')}"
        anti = pain_rationale.get("anti_patterns", [])
        if anti:
            base += f"\nAVOID THESE PATTERNS: {', '.join(anti)}"

    if combo_rationale:
        base += f"\n\nWHY THIS COMBO WORKS: {combo_rationale.get('why', '')}"
        exec_note = combo_rationale.get("execution_note", "")
        if exec_note:
            base += f"\nEXECUTION NOTE: {exec_note}"
        what_not = combo_rationale.get("what_not_to_do", "")
        if what_not:
            base += f"\nDO NOT: {what_not}"

    return base.strip()
```

**Test after Improvement 5:**
- CQ `depth` dimension should improve (more context-grounded briefs)
- `why_this_works` field in each brief should reference the specific combo/pain rationale
- Full 5-creator benchmark should show CQ increase

---

## Test Loop Protocol

After EACH improvement, run:
```bash
python3 test_5creators.py http://localhost:8000 2>&1 | tee /tmp/bench_imp_N.txt
```

Watch for:
- Avg CQ: should not drop below 770. If it does → STOP, revert, diagnose.
- Field completeness 5/5: must stay there. If any field fails → read that brief manually.
- Generation time: must stay < 90s per run.
- After Imp 1: check `signature_phrases_used` appears with ≥2 phrases
- After Imp 4: check `validation_passed: true` in all briefs

Save benchmark result for each improvement to compare.

---

## Commit Protocol

After each improvement passes tests:
```bash
cd /Users/mosaic/Downloads/magcontentinator_webapp
git add stages/generator.py  # (+ ashwamag_config.py for imp 5)
git commit -m "improvement N: <description>

Co-Authored-By: Paperclip <noreply@paperclip.ing>"
```

Commit messages:
- Imp 1: `improvement 1: fix voice field mapping + inject voice examples as hard constraints`
- Imp 2: `improvement 2: enforce beat structure (4-6 typed beats, duration 55-65s)`
- Imp 3: `improvement 3: archetype-specific generation constraints`
- Imp 4: `improvement 4: post-generation validation checklist`
- Imp 5: `improvement 5: library rationale and combo execution context`

---

## Phase 3: Production Deploy

After all 5 improvements pass local benchmark:

```bash
cd /Users/mosaic/Downloads/magcontentinator_webapp
git push
```

Wait 2-3 minutes for Railway auto-deploy. Then:
```bash
python3 test_5creators.py https://stellar-youth-production.up.railway.app 2>&1 | tee /tmp/bench_prod_final.txt
```

**Pass criteria for production:**
- All 5 creators: PASS
- Avg CQ ≥ 850 (up from 815)
- All field completeness 5/5
- All briefs: `validation_passed: true`
- All briefs: `signature_phrases_used` with ≥2 phrases
- Generation time < 60s per creator

Append results to `docs/REVIEW_BY_ALPHA.md` under a new section:
```markdown
## Phase 3: Final Production Benchmark — [DATE]

[Paste benchmark table here]

Verdict: [READY / NOT READY + blockers]
```

---

## AP6 Flags — Get Clarification Before Starting If Possible

These were flagged in the review. If Pranav hasn't clarified before Phase 2 starts, use these defaults:

1. **Beat type flexibility**: Use minimum 4 required (hook + solution + proof + cta), others optional, max 6. This is the safest interpretation that won't cause generation failures.

2. **Improvement 1 scope**: Bundle voice field mapping fix WITH Improvement 1. They're inseparable — testing voice examples without fixing the key names gives misleading results.

3. **Archetype constraint dict keys**: Use archetype GROUPS (from `ARCHETYPE_GROUPS`), not individual archetypes. Use `get_archetype_group()` for lookup.

4. **Quick wins QW-1/QW-2/QW-3**: Defer unless explicitly approved. Don't add scope without authorization.

---

## Failure Modes and Recovery

| Failure | Diagnosis | Recovery |
|---------|-----------|----------|
| CQ drops < 770 | Read a failing brief manually — which dimension dropped? | Revert that improvement, re-analyze |
| `signature_phrases_used` missing | Model ignoring output format addition | Strengthen instruction: add to CoT checklist too |
| `validation_passed` absent | JSON parsing issue or model ignoring field | Check output format instructions — ensure field is in schema |
| Beat count > 6 | Model generating too many beats | Verify truncation fallback in `_parse_brief_json()` is active |
| Generation fails (exception) | JSON parse error due to new schema fields | Check `_parse_brief_json()` — new fields shouldn't cause parse errors |
| Archetype lookup KeyError | Unrecognized archetype value | Verify `get_archetype_group()` fallback returns "ugc_authentic" |

---

## Summary: What You're Changing

| Improvement | File | Lines affected | Risk |
|-------------|------|----------------|------|
| 1 (voice field fix + examples) | generator.py | ~40 lines in `_build_system_prompt()` + OUTPUT_FORMAT_INSTRUCTIONS | Low |
| 2 (beat structure) | generator.py | ~20 lines in OUTPUT_FORMAT_INSTRUCTIONS + system prompt + `_parse_brief_json()` | Medium |
| 3 (archetype constraints) | generator.py | ~60 lines new dict + ~10 lines in `_build_system_prompt()` | Low |
| 4 (validation checklist) | generator.py | ~20 lines replacing cot_block | Low |
| 5 (library rationale) | ashwamag_config.py | ~80 lines new dicts + update `build_library_context()` | Low |

**Total**: ~230 lines changed across 2 files. Surgical. No architecture changes.
