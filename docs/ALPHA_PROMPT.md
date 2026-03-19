# ALPHA — Task: Magcontentinator Review + Improvement Sprint

---

## Context

You are being assigned a task on **Magcontentinator** — a different project from Creator Portal. This is a FastAPI webapp that generates TikTok content briefs for the RootLabs CRE team.

**Working directory**: `/Users/mosaic/Downloads/magcontentinator_webapp/`

Start by reading all context docs:
```
docs/CONTEXT.md           — What it is, who uses it, constraints
docs/PIPELINE.md          — Full 6-stage architecture
docs/ARCHITECTURE_REVIEW.md — Current state assessment (7.3/10)
docs/IMPROVEMENTS.md      — The 5 approved improvements with full spec
docs/TESTING.md           — Playwright benchmark + deploy guide
```

Also read the key source files:
```
stages/generator.py       — Stage E (most important — this is where improvements land)
stages/voice.py           — Stage D (voice fingerprinting)
stages/profiler.py        — Stage C (archetype classification)
ashwamag_config.py        — Product intelligence + compliance rules
templates/index.html      — The full UI (single file — 3 screens)
pipeline.py               — Job state + stage orchestration
```

---

## Phase 1: Comprehensive Review (DO THIS FIRST)

Before touching any code, produce a thorough review document saved to:
`docs/REVIEW_BY_ALPHA.md`

Your review must cover:

### 1. Architecture Review
- Validate or challenge the 7.3/10 rating
- Are there issues the previous review missed?
- Is the stage decomposition optimal for this use case?
- Any risks or technical debt that should be addressed?
- Is the SSE streaming + job state design solid for Railway (see AP23: no in-memory durable state)?

### 2. User Experience Review
- Read `templates/index.html` carefully (all 3 screens + JavaScript)
- Is the 3-screen flow (Input → Intent → Briefs) right for an internal AM tool?
- Is there friction that shouldn't exist?
- Is the feedback/regen loop in Screen 3 well designed?
- What's missing that would make this tool sticky for daily use by 6 PMs?

### 3. Prompt Quality Review
- Read `stages/generator.py` fully — especially `_build_system_prompt()`
- Is the system prompt structured optimally?
- Are there token inefficiencies?
- Does the chain-of-thought grounding actually work?
- Is CQ scoring (GPT-4o) in `_score_brief()` well calibrated?

### 4. Stage E Input Utilization
- Trace exactly what data flows from each upstream stage into Stage E
- Identify what's available but not used
- Identify what's used but not effectively

### 5. Improvement Plan Validation
- Read `docs/IMPROVEMENTS.md` — the 5 approved improvements
- Do you agree with the approach for each?
- Are there gaps or better ways to implement them?
- What order would you recommend?
- Are there any quick wins not in the list?

### 6. Risk Assessment
- What's the riskiest thing to change? Why?
- What should NOT be touched?
- What's the kill criteria for an improvement that makes CQ worse?

---

## Phase 2: Implement Improvements + Test Loop

After writing the review doc, implement the 5 improvements from `docs/IMPROVEMENTS.md` **in order**.

For each improvement:
1. Implement the change (surgical — don't refactor what isn't part of the improvement)
2. Run `python3 test_5creators.py http://localhost:8000` against local server
3. Compare results to baseline (docs/TESTING.md has baseline numbers)
4. If CQ drops or field completeness drops, diagnose and fix before moving on
5. Commit with a clear message: `improvement 1: use voice examples in stage E`
6. Move to next improvement

**Test loop for stubborn issues**:
If a test run fails or quality drops:
- Read the failing brief output carefully
- Identify which prompt instruction is being ignored
- Tighten that constraint specifically
- Re-run
- Repeat until passing

**Target after all 5 improvements**:
- Avg CQ ≥ 850 (baseline: 815)
- All field scores 5/5
- All briefs include `validation_passed: true`
- All briefs include `signature_phrases_used: [...]` with ≥2 phrases
- Archetype confidence ≥ 80% average (unchanged — this is profiler, not generator)

---

## Phase 3: Final Deploy

Once all 5 improvements are passing locally:
1. Push to production: `git push` (Railway auto-deploys)
2. Wait ~2 min for deploy
3. Run full benchmark against production: `python3 test_5creators.py`
4. Confirm results match or exceed local results
5. Write final status to `docs/REVIEW_BY_ALPHA.md` (append to bottom)

---

## Constraints

- **No evaluator stage** — regen loop is the quality control mechanism
- **No reliability multiplier** — not needed
- **No library data expansion** — improve how library intel is used, not the data
- **No refactoring outside improvement scope** — only change what you need to
- **Compliance is critical** — never loosen BANNED_ANGLES, BANNED_PHRASES, or VALID_CLAIMS
- **AP6: Ask before guessing** — if anything is ambiguous, flag it in the review doc

---

## Deliverable After Phase 1

Save your complete review to `docs/REVIEW_BY_ALPHA.md`. This is a formal deliverable — Pranav will review it before you start Phase 2. Make it substantive. Follow AP15: files over chat.

Format:
```markdown
# Magcontentinator — Alpha Review

## Rating: X/10 (my assessment)
[Overall verdict in 2-3 sentences]

## Architecture: [rating]
[Findings]

## UX: [rating]
[Findings]

## Prompt Quality: [rating]
[Findings]

## Improvement Plan Assessment
[Per-improvement: Agree/Modify/Flag + reasoning]

## Risks
[What not to touch, kill criteria]

## My Recommended Changes (beyond the 5 approved)
[Optional additions or modifications]
```
