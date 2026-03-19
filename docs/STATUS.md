# Magcontentinator — Status as of 2026-03-19

## What Was Done (This Sprint)

### Phase 1 — Architecture Review
Full codebase review completed. Key finding: **voice field name mismatch** — Stage D produces 11 fields but Stage E was reading wrong key names (`pacing` instead of `speaking_pace`, `dont` instead of `avoid`, etc.), silently dropping 8/11 voice fields. Documented in `REVIEW_BY_ALPHA.md`.

### Phase 2 — 5 Improvements Implemented

All implemented in `stages/generator.py` + `ashwamag_config.py`. Committed and deployed to Railway.

| # | Improvement | What Changed | Status |
|---|-------------|-------------|--------|
| 1 | Voice field fix + examples | Fixed 8 wrong key names; injected `example_hook_in_their_voice` + `example_cta_in_their_voice` as hard constraints; added `signature_phrases_used` output field | ✅ Done |
| 2 | Beat structure enforcement | Added typed `beat_type` (hook/problem/solution/proof/cta), `total_beats` 4-6 required, `estimated_duration` 55-65s, truncation fallback | ✅ Done |
| 3 | Archetype constraints | Added `ARCHETYPE_CONSTRAINTS` dict for 7 groups; injected per-brief required approach, forbidden hooks, CTA style | ✅ Done |
| 4 | Validation checklist | Extended CoT block with 8-point compliance checklist; added `validation_passed` field | ✅ Done |
| 5 | Library rationale | Added `LIBRARY_RATIONALE` + `COMBO_RATIONALE` dicts; injected "why it converts" + anti-patterns + execution notes into library context | ✅ Done |

### Phase 3 — Production Benchmark

Run 2026-03-19 against `https://stellar-youth-production.up.railway.app`:

```
Creator            Status   Preflight   Generate   Arch Conf   Videos   CQ Avg   CQ Top   Fields
rphreviews         PASS     182s        36s        99%         10/10    812      837      5/5
iamvictoriadoss    PASS     166s        40s        92%         10/10    803      814      5/5
bribez1            PASS     169s        40s        90%         10/10    809      815      5/5
theaustinbrown     PASS     157s        35s        82%         10/10    828      849      5/5
bischjj            PASS     118s        35s        98%         10/10    817      826      5/5

PASS: 5  FAIL: 0  TIMEOUT: 0
Avg preflight: 158s
Avg generation: 37s
Avg CQ: 813/1000  (baseline was 815 — flat, within noise)
```

**Voice differentiation is working** (hooks sound like each creator). CQ metric is flat because the rubric measures structural quality, not voice authenticity — which is fine since we are NOT optimizing for CQ anymore.

---

## What's NOT Done (Next Phase)

See `NEXT_TASKS_FOR_ALPHA.md` for the full task specification.

**Critical:**
1. `sleep-score` strategy selection is broken — it's just a label, doesn't change anything
2. Regen UX is blocking — overlay prevents reading other briefs while one regenerates
3. Beat time field: renders use `beat.time` (old) but new schema uses `beat.time_range`

**Important:**
4. Input calibration audit — does each selection actually reach the prompt?
5. UX timing — 150-180s preflight with minimal feedback, opportunity to show progressive value
6. Regen prompt quality — feedback is injected as raw text, could be structured better

---

## Architecture (Quick Reference)

- Working dir: `/Users/mosaic/Downloads/magcontentinator_webapp/`
- Prod URL: `https://stellar-youth-production.up.railway.app`
- Railway auto-deploys on push to main (~2 min)
- Main pipeline files: `stages/generator.py`, `ashwamag_config.py`, `pipeline.py`, `main.py`, `templates/index.html`
- Test: `python3 test_5creators.py [URL]`

---

## What We Are NOT Optimizing For

- CQ score (815 baseline, leave it)
- Reliability (5/5 PASS, leave it)
- Generation speed (35-40s, acceptable)

## What We ARE Optimizing For

1. **Input calibration** — does each user selection actually change the output?
2. **Strategy routing** — sleep-score, gmv-max, custom should produce meaningfully different briefs
3. **UX seamlessness** — non-blocking regen, better loading states, progressive value during preflight
4. **Regen quality** — feedback should be parsed and used to produce the specific intended change
