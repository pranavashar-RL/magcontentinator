# Magcontentinator — Project Context

## What This Is

Magcontentinator is an **internal AI tool** for the RootLabs CRE (Creator Relations) team at Mosaic Wellness. It generates TikTok content briefs for creators promoting **AshwaMag Gummies** — a magnesium + ashwagandha supplement.

**Who uses it**: Account Managers and CRE PMs who manage creator relationships. They paste a TikTok handle, set their intent, and get 3 ready-to-send content briefs with beat-by-beat scripts.

**Why it exists**: Manually briefing 31+ creators across campaigns is slow and inconsistent. This tool applies GMV-validated library patterns + deep creator voice profiling to generate briefs that feel authentic to each creator and are optimized for AshwaMag conversion.

---

## Live Deployment

- **Production URL**: `https://stellar-youth-production.up.railway.app`
- **Platform**: Railway (auto-deploys on git push to main)
- **Stack**: FastAPI + Jinja2 + Vanilla JS + SSE streaming
- **Python**: 3.11
- **Key APIs**: Apify (TikTok scraping), rl-video-analyzer (Gemini 2.5 Flash visual analysis), OpenAI GPT (profiling, voice, brief generation, scoring)

---

## Codebase Location

```
/Users/mosaic/Downloads/magcontentinator_webapp/
├── main.py                  — FastAPI routes
├── pipeline.py              — Job state + stage orchestration
├── ashwamag_config.py       — Product intelligence (single source of truth)
├── stages/
│   ├── scraper.py           — Stage A: Apify TikTok scraping
│   ├── analyzer.py          — Stage B: Visual analysis via rl-video-analyzer
│   ├── profiler.py          — Stage C: Archetype + identity classification
│   ├── voice.py             — Stage D: Voice fingerprinting
│   ├── library.py           — Library intel lookup
│   ├── inspiration.py       — Inspiration URL digest
│   └── generator.py         — Stage E: Brief generation + CQ scoring
├── templates/index.html     — Single-page frontend (3 screens, SSE)
├── test_5creators.py        — Playwright E2E benchmark (5 top-GMV creators)
├── test_e2e.py              — Basic E2E test
└── docs/                    — YOU ARE HERE
```

---

## User Experience Flow

**Screen 1 — Creator Input**
- Enter TikTok handle (e.g. `rphreviews`)
- Optional: add inspiration URLs (reference TikTok videos) + note
- Hit "Continue" → immediately transitions to Screen 2 + starts background preflight

**Screen 2 — Intent Setting** (while preflight runs in background)
- Status ribbon shows real-time pipeline progress (A→B→C→D steps)
- User sets strategy (Creator's Best / GMV Max / Sleep Score / Custom) + writes angle/direction
- Library Intel card appears when preflight completes (shows GMV-validated pain point + combo)
- "Taking long? → Use transcripts" button appears at 45s if preflight not complete (fallback)
- User hits "Generate 3 briefs" → transitions immediately to Screen 3 with skeleton loading

**Screen 3 — Briefs**
- 3 tabs: Brief 1, Brief 2, Brief 3
- Left panel: full brief (hook card + beat table + metadata)
- Right panel: Quality Score (CQ /1000 with dimension breakdown) + Feedback section
- User can give feedback + regenerate any individual brief (keeps others intact)
- Copy brief / Copy creator message buttons

---

## Product: AshwaMag Gummies

- **Brand**: RootLabs
- **Format**: Gummy with visible beadlets inside
- **Key differentiator**: Beadlet technology — you can SEE the beadlets (visual proof of delivery)
- **Claims**: See `ashwamag_config.py` → `VALID_CLAIMS` for the exact allowed list
- **Banned**: Anxiety, weight_body_comp angles + all disease treatment claims
- **Target audience**: Women (primary)

---

## Key Constraints

1. **No evaluator stage** — users give feedback directly via the UI; the feedback + regen loop IS the quality control
2. **No reliability multiplier** — out of scope
3. **No library combos data expansion** — library data is static; we improve HOW we use it, not the data itself
4. **Compliance is critical** — VALID_CLAIMS and BANNED_PHRASES/BANNED_ANGLES from `ashwamag_config.py` are hard rules
5. **Memory is in-memory only** — JOBS dict; jobs are lost on restart (by design for now)
