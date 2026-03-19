# Magcontentinator — ALPHA Review
**Date**: 2026-03-19
**Reviewer**: ALPHA (CEO Agent, RootLabs CRE)
**Scope**: Full codebase + docs review before Phase 2 implementation

---

## Overall Rating: 6.8/10 ↓ from 7.3

The previous 7.3 rating missed a critical data flow bug that makes the system materially worse than it should be. Corrected to 6.8. The bones are solid — async pipeline, SSE streaming, clean stage separation — but the generator is operating on a severely degraded voice fingerprint.

---

## 1. Architecture Review

### 1.1 Per-Stage Revised Ratings

| Stage | Previous | ALPHA | Delta | Key Finding |
|-------|----------|-------|-------|-------------|
| A — Scraper | 8.5 | 8.5 | — | Clean. No issues. |
| B — Analyzer | 6.5 | 6.5 | — | 60% field discard confirmed. Acceptable given constraint. |
| C — Profiler | 6.8 | 7.0 | +0.2 | Better than rated — aggregation approach is sound, per-video breakdown is useful |
| D — Voice | 6.0 | 5.0 | -1.0 | **WORSE than documented.** Not just examples missing — field names wrong. |
| E — Generator | 5.5 | 5.0 | -0.5 | Receives partially broken voice input; no brief-type differentiation in system prompt |

### 1.2 Critical Bug NOT in Previous Review: Voice Field Name Mismatch

This is the most important finding. `stages/voice.py` produces this schema:
```
tone, vocabulary_level, signature_phrases, speaking_pace, hook_style,
cta_style, educational_style, authenticity_markers, avoid,
example_hook_in_their_voice, example_cta_in_their_voice
```

`stages/generator.py` `_build_system_prompt()` reads these keys:
```python
("tone", "Tone"),           # ✅ matches
("vocabulary_level", "Vocabulary"), # ✅ matches
("energy", "Energy"),       # ❌ NOT in voice schema — always None
("delivery_style", "Delivery style"), # ❌ NOT in voice schema — always None
("pacing", "Pacing"),       # ❌ voice has "speaking_pace" — always None
("humor_style", "Humor style"), # ❌ NOT in voice schema — always None
```
And:
```python
voice.get("do") or []       # ❌ voice has no "do" key — always empty
voice.get("dont") or []     # ❌ voice has "avoid", not "dont" — always empty
```

**Net result**: Of the 11 voice fields generated, the generator actually uses **3**: `tone`, `vocabulary_level`, `signature_phrases`. The following are silently discarded:
- `speaking_pace` (generator reads `pacing`)
- `avoid` list (generator reads `dont`)
- `hook_style` (unread)
- `cta_style` (unread)
- `educational_style` (unread)
- `authenticity_markers` (unread)
- `example_hook_in_their_voice` (unread — documented bug)
- `example_cta_in_their_voice` (unread — documented bug)

This means **Improvement 1 cannot be completed correctly without also fixing the field name mapping**. The spec in IMPROVEMENTS.md is directionally right but will leave 5 additional voice fields orphaned if not addressed simultaneously.

**Fix required** (add to Improvement 1):
```python
# In _build_system_prompt(), replace mismatched reads with correct keys:
("pacing", "Pacing")           →  ("speaking_pace", "Pacing")
("dont", "DON'T voice rules")  →  ("avoid", "AVOID")
# Also add new reads for previously ignored fields:
("hook_style", "Hook style")
("cta_style", "CTA style")
("educational_style", "Educational style")
```

### 1.3 System Prompt Has No Per-Brief Differentiation

`_build_system_prompt()` is called identically for briefs 1, 2, and 3. The `brief_num` parameter is passed but only used to check library selection (`brief_key = f"brief_{brief_num}"`). Every brief gets:
- Same identity block
- Same voice block
- Same compliance block
- Same chain-of-thought block

The per-brief differentiation only lives in `_build_user_prompt()`. This is architecturally fine but means Improvement 3 (archetype constraints) needs to either go into user prompt or use brief_num to vary the system prompt.

**Recommendation**: Keep archetype constraints in system prompt (it's still the better structural location), and make the archetype constraint block static for all 3 briefs since it's creator-level, not brief-level.

### 1.4 SSE + In-Memory Job State — Railway Compatible

The design is correct for Railway:
- `asyncio.Queue` per client — no shared mutable state across requests
- `events[]` replay buffer for late subscribers — handles reconnects correctly
- 30s keepalive prevents Railway's request timeout
- In-memory JOBS dict is explicitly in-scope per CONTEXT.md

One minor risk: no job TTL. If the server runs for days under high load, JOBS dict grows unbounded. Not urgent given usage pattern (6 PMs, ~1-2 jobs/hour), but worth noting.

### 1.5 Library Stage: Sync in Async

`library.py` is `run_sync()` called from `async def run()`. This blocks the event loop for the duration of the dict lookup. Since it's pure Python with no I/O, the wall time is ~1ms. No problem in practice — correct to leave as-is.

### 1.6 Stage B → Stage E Data Discard

Of the 37 B1 fields, two are particularly valuable and currently ignored by Stage E:
- `product_first_appear_second`: the creator's actual pattern for when they introduce product — would let the generator match their style
- `hook_duration_seconds` (or derived from beats): the creator's typical hook length — informs beat timing in Improvement 2

Not in the 5 improvement scope, but worth flagging for a future sprint.

---

## 2. User Experience Review

**Overall UX Rating: 8.0/10** — Well-designed for an internal AM tool. The friction is in the right places.

### 2.1 What Works

- **3-screen flow** is correct for this use case. Internal PMs are not consumer users — they understand they're configuring a pipeline
- **Background preflight on Screen 1 → 2 transition** is smart — uses transit time productively
- **Library Intel card** appearing mid-wait gives PMs something to validate before generating
- **45s transcript skip button** is good UX recovery for slow analysis
- **Skeleton loading on Screen 3** sets clear expectations during 30-35s generation
- **Single-brief regen** with feedback preserved — technically correct and PMs won't abuse it
- **Copy brief / Copy creator message** buttons serve the actual workflow (pasting into Notion/Slack)

### 2.2 Gaps

1. **No structured export** — PMs likely want TSV/CSV or formatted copy for Airtable/Notion paste. "Copy brief" is useful but doesn't format for a spreadsheet. *Not blocking for Phase 2 but worth noting.*

2. **No voice fingerprint visibility** — PMs on Screen 3 can't see the archetype or voice profile that drove the generation. A collapsed "About this creator" section would help PMs understand why a brief sounds the way it does and give better regen feedback.

3. **Strategy "Custom" requires intent textarea** but UI doesn't make this obvious — Custom mode silently deselects all presets; the textarea label says "Additional direction (optional)" which undersells its role when strategy=Custom.

4. **No brief comparison mode** — PMs must click tabs to compare. For 3 briefs this is acceptable; not a blocker.

5. **Production notes field not rendered in the UI** — `production_notes` is generated in the brief JSON but is not displayed in Screen 3's brief panel. This is useful information for PMs to relay to creators.

### 2.3 Regen Loop Assessment

The feedback → regen loop is well-designed. Key observations:
- Feedback is injected as `REGENERATION FEEDBACK (previous version was rejected — fix these issues): {feedback}` in the user prompt — this is strong and clear
- The other briefs are preserved (brief_map logic in generator.py is correct)
- Re-scoring happens immediately after regen — CQ updates correctly

One gap: when regenerating, the same system prompt is used. If the original brief had a compliance issue, the validation checklist (Improvement 4) will catch it on regen. But there's no memory of "previous version had X problem" beyond what the user types. This is acceptable.

---

## 3. Prompt Quality Review

**Overall Prompt Rating: 7.5/10**

### 3.1 System Prompt Structure Assessment

The 10-section structure is logical and well-ordered. Sections in priority order (what GPT attends to most = later in prompt): CoT instructions → output format → compliance → library intel → voice → identity → product. This ordering roughly matches attention weighting.

**Section-by-section issues:**

| Section | Rating | Issue |
|---------|--------|-------|
| 1. Role | 8/10 | Clear. "Your job is to create beat-by-beat content briefs for AshwaMag Gummies" is appropriately narrow |
| 2. Product context | 9/10 | FORMULATION is comprehensive and specific (beadlet detail, absorption claim, COA) |
| 3. Creator identity | 7/10 | Falls back to archetype string when identity_constants missing — acceptable |
| 4. Voice fingerprint | 4/10 | **3 of 11 fields actually injected due to key mismatch bug** |
| 5. Library intel | 7/10 | Pain point + combo + GMV numbers are good. Missing rationale (Improvement 5 fixes this) |
| 6. Inspiration | 8/10 | Clean conditional injection |
| 7. Compliance | 9/10 | Comprehensive and hard. BANNED_PHRASES list is explicit. |
| 8. Content strategy | 8/10 | Good data-grounded rules. Authority premium (28x) and transformation gap stats are useful anchors |
| 9. Chain-of-thought | 6/10 | 5 steps are reasonable but step 1-2 are redundant when voice/profile are well-populated. Not harmful, ~200 tokens |
| 10. Output format | 7/10 | Detailed field specs. Missing: beat count constraint, beat type constraint, duration constraint (Improvement 2 fixes) |

### 3.2 Token Efficiency

Current system prompt is approximately 2,200-2,800 tokens depending on voice/library content. With all 5 improvements:
- Improvement 1 adds ~200 tokens (voice examples + constraint header)
- Improvement 2 adds ~150 tokens (beat structure rules)
- Improvement 3 adds ~150 tokens (archetype constraint block)
- Improvement 4 adds ~200 tokens (validation checklist)
- Improvement 5 adds ~200 tokens (library rationale)

Total post-improvements: ~3,100-3,700 tokens. Well within GPT-5.4 context limits. No token budget concerns.

### 3.3 Chain-of-Thought Placement

The CoT is in the system prompt, identical for all 3 briefs. This is slightly suboptimal — step 1 asks "what pain point hooks this creator's audience?" which should be answered differently for brief 1 vs brief 3. But the actual differentiation is in the user prompt via `brief_type` and `brief_desc`, so the CoT just provides the reasoning framework.

No structural change recommended here — the slight token waste (~200 tokens × 3 calls = 600 extra tokens) is acceptable.

### 3.4 CQ Scoring Calibration

The 10-dimension scoring at temperature 0.2 is well-designed. Current avg CQ 815 with a range of ~808-822 across 5 creators suggests scoring is consistent. The grade computation is re-calculated from dimension sums (not trusted from LLM) — this is correct engineering.

One gap: CQ scoring doesn't know the brief type. A `gmv_max` brief should score higher on `product_presentation` (direct commerce intent) while a `creators_own` brief should score higher on `ease_of_execution` (authenticity fit). Adding brief type context to the CQ prompt would give more meaningful scores.

**Not blocking for Phase 2** but worth a future improvement.

---

## 4. Stage E Input Utilization

### Full Data Availability vs. Usage Trace

| Field | Available from | Stage E uses? | Assessment |
|-------|---------------|---------------|------------|
| tone | voice.py | ✅ Yes | Used correctly |
| vocabulary_level | voice.py | ✅ Yes | Used correctly |
| signature_phrases | voice.py | ✅ Yes | List, used correctly |
| speaking_pace | voice.py | ❌ No (key mismatch: reads `pacing`) | Bug — fix in Improvement 1 |
| hook_style | voice.py | ❌ No (unread key) | Bug — fix in Improvement 1 |
| cta_style | voice.py | ❌ No (unread key) | Bug — fix in Improvement 1 |
| educational_style | voice.py | ❌ No (unread key) | Bug — add in Improvement 1 |
| authenticity_markers | voice.py | ❌ No (unread key) | Bug — add in Improvement 1 |
| avoid | voice.py | ❌ No (key mismatch: reads `dont`) | Bug — fix in Improvement 1 |
| example_hook_in_their_voice | voice.py | ❌ No (documented gap) | Fix in Improvement 1 |
| example_cta_in_their_voice | voice.py | ❌ No (documented gap) | Fix in Improvement 1 |
| archetype | profile.py | ✅ Via identity_block | Used |
| identity_constants | profile.py | ✅ Yes | Used well |
| dominant_pain_points | profile.py | ✅ Via user prompt (brief 3) | Used |
| strengths/gaps | profile.py | ❌ No | Available but ignored — minor miss |
| pain_point claims | library.py | ✅ Yes | Good |
| hooks_that_convert | library.py | ✅ Yes | Good |
| visual_proof elements | library.py | ✅ Yes | Good |
| pain_point rationale | library.py | ❌ No (doesn't exist yet) | Improvement 5 adds this |
| combo rationale | library.py | ❌ No (doesn't exist yet) | Improvement 5 adds this |
| product_first_appear_second | B1 per-video | ❌ No | Future sprint |
| transformation_proof_rate | profile.py | ❌ No | Could be useful context |

### Summary
Currently using ~7 of ~20+ available data fields in Stage E. Post-improvements will reach ~15. The biggest single-impact fix is the voice field name mismatch (affects 8 fields).

---

## 5. Improvement Plan Validation

### Improvement 1: Voice Examples ✅ AGREE — but scope expansion needed

**Assessment**: Correct direction, but the spec only addresses the examples gap. The field name mismatch is a prerequisite that must be fixed first.

**Recommended expanded scope for Improvement 1:**
```python
# Step A: Fix field name mismatches in _build_system_prompt():
# speaking_pace → read with key "speaking_pace" (not "pacing")
# avoid → read with key "avoid" (not "dont")
# Add hook_style, cta_style, educational_style as new voice lines

# Step B: Add examples as hard constraints (per spec)
# Step C: Add "signature_phrases_used" to output format (per spec)
```

This is still "one function, ~40 line change" — appropriate scope.

**Token impact**: +200 tokens/call. Fine.

**Risk**: Low. Additive to system prompt. Worst case: model ignores some fields.

### Improvement 2: Beat Structure Enforcement ✅ AGREE — with one clarification

**Assessment**: The beat structure spec is good. Required types `hook|problem|solution|proof|cta` maps to real TikTok structure.

**Clarification needed**: The spec says "Required beat types: hook, problem, solution, proof, cta" but also says "total beats: 4, 5, or 6". These are in tension — if exactly 5 beat types are required, total must be exactly 5. If 4 or 6 are allowed, the model needs flexibility on which beat types to include/expand.

**Recommendation**: Change spec to "Beat types must appear in this order: hook → [problem] → solution → [proof] → cta, where [] = optional. Minimum 4 beats (hook + solution + proof + cta), maximum 6."

**Risk**: Medium. JSON parsing of beats is already working. Adding `beat_type` field is additive. The strict count (4-6) might cause rare JSON validation failures where model writes 7 beats — add a truncation fallback in `_parse_brief_json()`.

### Improvement 3: Archetype-Specific Constraints ✅ AGREE — with key name alignment fix

**Assessment**: The `ARCHETYPE_CONSTRAINTS` dict in the spec uses keys `pharmacist`, `wellness_lifestyle`, `fitness`, `direct_commerce`. But Stage C's archetype output is granular (e.g., `wellness_influencer`, not `wellness_lifestyle`). Must use `get_archetype_group()` from `ashwamag_config.py` to map archetype → group → constraint block.

**Recommendation**: Key the constraint dict by archetype GROUP (`medical_authority`, `wellness_lifestyle`, `fitness`, `direct_commerce`, `ugc_authentic`, `blue_collar_rural`, `reaction_story`) and use `get_archetype_group(profile["archetype"])` to look up. Add fallback to `ugc_authentic` for unrecognized archetypes.

**Risk**: Low. Pure additive system prompt text. Worst case: model ignores the constraints block.

### Improvement 4: Post-Generation Validation Checklist ✅ AGREE — Option A is correct

**Assessment**: Adding `validation_passed: true` to the output format is a strong forcing function. The 8-check list is well-calibrated.

**One addition**: Add "Are signature_phrases_used populated with ≥ 2 phrases from the voice profile?" to the checklist, since Improvement 1 adds that field and validation should confirm it.

**Risk**: Low. Additive prompt instruction. One failure mode: model writes `validation_passed: true` without actually checking. This is detectable via the test benchmark (check if BANNED_PHRASES appear in briefs).

### Improvement 5: Library Rationale ✅ AGREE — well-specified

**Assessment**: The spec is complete. Adding `LIBRARY_RATIONALE` and `COMBO_RATIONALE` dicts to `ashwamag_config.py` is the right location.

**One flag**: The `stress_cortisol` pain point has hooks_that_convert including "cortisol levels through the roof" — this language is very close to the BANNED behavior of cortisol-face framing. The rationale should include an anti-pattern note that cortisol language must stay at "stress recovery support" level and never imply physical symptoms or appearance changes. Add: `"anti_patterns": ["cortisol face/belly imagery", "stress = weight gain framing", "direct cortisol reduction claim"]`.

**Risk**: Low. Additive context in `ashwamag_config.py` and library injection. No code logic change.

### Recommended Implementation Order: Same as spec (1→2→3→4→5)

Order is correct. Improvement 1 unlocks the most latent quality from existing pipeline. Improvement 2 structures the output before adding constraints (3) and validation (4). Improvement 5 is additive context and can come last.

---

## 6. Quick Wins Not in the 5 Improvements

These are small changes that would improve quality without being in the approved improvement plan. Noting for awareness:

### QW-1: Add `strengths` and `gaps` to Stage E context
Profile already generates `strengths` (up to 3 content strengths) and `gaps` (up to 3 vs AshwaMag best practices). Neither is injected into Stage E. A single line:
```python
gaps = profile.get("gaps") or []
if gaps:
    voice_lines.append(f"- Known gaps to address: {', '.join(gaps)}")
```
could add "low transformation proof" or "never shows product demo" as context. 2-line change, no risk.

### QW-2: Add brief type to CQ scoring context
Currently the scorer has no idea if it's scoring a `gmv_max` or `creators_own` brief. Adding `"Brief type: {brief_type}" ` context would calibrate dimension weights appropriately.

### QW-3: Pass `product_first_appear_second` avg to Stage E
The B1 analysis includes `product_first_appear_second` per video. Computing the average across analyzed videos and passing it as "Creator typically introduces product at ~{avg}s" would help the generator match the creator's natural product introduction pattern.

---

## 7. Risk Assessment

### Riskiest Changes

1. **Improvement 2 (Beat Structure)** — strictest schema change. Enforcing `beat_type` enum + count range (4-6) means any brief where the model generates 3 or 7 beats will fail JSON validation. **Mitigation**: Add a lenient parse fallback in `_parse_brief_json()` that tolerates beat count violations rather than crashing — log a warning, return anyway.

2. **Improvement 1 + voice field fix together** — fixing 8 fields at once means if the voice model's output quality is variable, the quality delta could go either way. **Mitigation**: Test Improvement 1 (with field fixes) against a single creator before running the full 5-creator benchmark.

### What NOT to Touch

- `ashwamag_config.py` → `BANNED_ANGLES`, `BANNED_PHRASES`, `BANNED_VISUALS`, `VALID_CLAIMS` — compliance-critical, never loosen
- `stages/analyzer.py` — B1 analysis is working well (37-field output, Gemini visual analysis)
- `stages/scraper.py` — clean, don't touch
- `pipeline.py` — SSE design is correct, in-memory is by design
- `main.py` — routes are clean, no changes needed

### Kill Criteria

If avg CQ drops below **770** after any single improvement, roll back that improvement before continuing.

If field completeness drops below **4/5** for any creator, investigate before proceeding.

If generation time exceeds **90s** for any brief, check Stage E prompt token size.

---

## 8. Final Architecture Rating

| Dimension | Rating | Notes |
|-----------|--------|-------|
| Stage decomposition | 8.5/10 | Clean A→B→C→D→E→score separation |
| Async/parallelism | 8.5/10 | 3× concurrent B1 analysis, 3× parallel generation, 3× parallel scoring |
| SSE design | 8.5/10 | Correct for Railway, keepalive, queue-per-client |
| Data flow integrity | 4.5/10 | Voice field mismatch is a significant structural bug |
| Prompt quality (current) | 6.5/10 | Good structure, broken voice injection, no beat constraints |
| Compliance architecture | 9.0/10 | Single source of truth, hard rules, baked in at generation |
| UX design | 8.0/10 | 3-screen flow well-suited to tool's purpose |
| Resilience | 7.5/10 | Transcript fallback, error handling, per-brief failure isolation |
| **Overall** | **6.8/10** | |

---

## 9. AP6 Flags — Ambiguities for Review Before Phase 2

These require Pranav's input before implementation:

1. **Beat type flexibility (Improvement 2)**: Should 5 beat types be required (exactly), or is 4 minimum with `problem` and `proof` as optional? The spec says 4-6 total and lists 5 required types — these are incompatible. **ALPHA recommends**: Minimum 4 required (hook + solution + proof + cta), others optional, max 6.

2. **Improvement 1 scope**: Should the voice field name mismatch fix be rolled into Improvement 1, or tracked as a separate pre-improvement fix? **ALPHA recommends**: Bundle it with Improvement 1 since you can't properly test Improvement 1's impact without fixing the underlying mapping.

3. **Archetype constraint dict keys**: Spec uses `pharmacist`, `wellness_lifestyle`, `fitness`, `direct_commerce` as top-level keys. But Stage C can produce 26 granular archetype values. Should the constraint dict use archetype GROUPS (from `ARCHETYPE_GROUPS`) or individual archetype values? **ALPHA recommends**: Use archetype groups — simpler, better coverage.

4. **QW-1/QW-2/QW-3**: Approve or defer these quick wins? They're each <5 lines but outside the 5 approved improvements.

---

## Phase 2 Readiness Assessment

| Check | Status |
|-------|--------|
| All context docs read | ✅ |
| Source code fully traced | ✅ |
| Critical bug found (voice field mismatch) | ✅ |
| Improvement specs validated | ✅ (with clarifications above) |
| Local server running | ❓ — verify before Phase 2 |
| Test benchmark accessible | ✅ — `test_5creators.py` ready |
| Baseline documented | ✅ — Avg CQ 815, 5/5 field completeness |

**Awaiting Pranav review of AP6 flags before starting Phase 2.**

---

*This document covers Phase 1. Phase 2 (implementation) begins after review.*
