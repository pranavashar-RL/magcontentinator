# Architecture Review — Current State Assessment

**Overall Rating: 7.3/10**
Solid production-ready MVP. Good stage decomposition, async parallelism, resilience. Significant gaps in voice utilization, brief constraints, and data flow efficiency.

---

## Per-Stage Scores

| Stage | Rating | Summary |
|-------|--------|---------|
| A — Scraper | 8.5/10 | Clean Apify integration, good metadata extraction |
| B — Analyzer | 6.5/10 | 37 fields extracted but only ~15 reach Stage E |
| C — Profiler | 6.8/10 | Sound aggregation; identity inference is brittle |
| D — Voice | 6.0/10 | Weakest data stage — synthetic examples generated but never used |
| E — Generator | 5.5/10 | Most under-constrained stage; beats unconstrained; no post-gen validation |

---

## Critical Data Flow Issues

### Issue 1: D → E Voice Examples Dropped
Stage D generates `example_hook_in_their_voice` and `example_cta_in_their_voice` — specific, crafted examples of how THIS creator would open and close a video. Stage E's system prompt injection includes only the voice key-value list; the examples are silently ignored.

**Result**: Briefs sound like "a creator who is authoritative" rather than sounding like THIS creator.

### Issue 2: B → C Lossy Reduction
Stage B extracts 37 fields per video. Stage C reduces this to ~8 aggregate metrics (counters). Beat-level scripts, product integration quality, and visual proof specifics are permanently discarded. Stage D reassembles from beat scripts — but only the top 5 videos.

### Issue 3: Library Context Shallow
Generator receives pain_point name + combo string + GMV numbers. No rationale ("why does relatable_callout × problem_solution convert?"), no anti-patterns, no archetype-specific success context.

### Issue 4: Beats Unconstrained
Generator can produce 2-beat or 8-beat briefs. No enforcement of beat types (hook/problem/solution/proof/CTA), no per-beat duration, no word count per beat. Production execution varies wildly.

### Issue 5: No Post-Generation Validation
Briefs are not checked before delivery:
- Did they use only VALID_CLAIMS?
- Are BANNED_PHRASES absent?
- Is there ≥1 transformation or social proof element?
- Does tone match voice profile?
- Is duration ~60s?

---

## What Works Well

1. **Stage decomposition** — clear input/output per stage, easy to modify independently
2. **Async parallelism** — 3 concurrent video analyses, 3 parallel brief generations, 3 parallel CQ scores
3. **SSE streaming** — real-time progress; user sees the pipeline moving
4. **Resilience** — transcript fallback if visual analysis fails; library fallback if confidence low
5. **Compliance baked in** — `ashwamag_config.py` is the single source of truth
6. **Regeneration flow** — user feedback → single brief regen → others preserved
7. **CQ scoring integrated** — every brief is scored immediately on 10 dimensions

---

## What Is Explicitly Out of Scope

The following were evaluated but are NOT part of the improvement plan:
- **No evaluator stage** — the regen feedback loop IS the evaluation mechanism
- **No reliability multiplier** — out of scope
- **No library data expansion** — static library is sufficient; improve usage, not data
- **No multi-creator batching** — single-creator-at-a-time by design
- **No job persistence** — in-memory is acceptable for now

---

## Comparison to V2 (Offline Pipeline)

The V2 pipeline (`/Users/mosaic/Downloads/video analysis/Magcontentinator_v2/`) runs offline against 31 creators and uses a richer architecture: Bayesian scoring, 46-sub-dimension CQ, related archetype cross-pollination, idea generation layer. The webapp is deliberately simpler — real-time, interactive, focused on single-creator brief generation.

The webapp should adopt specific V2 prompt quality improvements without adopting V2's computational complexity.
