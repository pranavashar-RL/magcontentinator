# Testing Guide

## E2E Benchmark — 5 Creators (`test_5creators.py`)

This is the main quality benchmark. Runs end-to-end against production, measures:
- Preflight time (Stage A→D)
- Generation time (Stage E)
- Archetype + confidence
- Videos analyzed (/10)
- CQ avg + top (/1000)
- Field completeness (/5)
- B1 source (gemini_visual vs gpt4o_transcript)

### Run against production
```bash
cd /Users/mosaic/Downloads/magcontentinator_webapp
python3 test_5creators.py
# or specify URL:
python3 test_5creators.py https://stellar-youth-production.up.railway.app
```

### Run against local server
```bash
# Terminal 1: start server
cd /Users/mosaic/Downloads/magcontentinator_webapp
uvicorn main:app --reload --port 8000

# Terminal 2: run test against local
python3 test_5creators.py http://localhost:8000
```

### Baseline Results (current production — 2026-03-19)
```
Creator            Status   Preflight   Generate   Arch Conf   Videos   CQ Avg   CQ Top   Fields
rphreviews         PASS     140s        32s        88%         10/10    820      850      5/5
iamvictoriadoss    PASS     165s        38s        82%         10/10    810      835      5/5
bribez1            PASS     158s        35s        79%         10/10    815      840      5/5
theaustinbrown     PASS     162s        37s        76%         10/10    808      830      5/5
bischjj            PASS     150s        33s        81%         10/10    822      845      5/5

PASS: 5  FAIL: 0  TIMEOUT: 0
Avg preflight: 155s
Avg generation: 35s
Avg CQ: 815/1000
```

**Quality target after improvements**: Avg CQ ≥ 850, all field scores 5/5, archetype confidence ≥ 80% average.

---

## Simple E2E Test (`test_e2e.py`)

Quick sanity check — tests a single creator:
```bash
python3 test_e2e.py
```

---

## Requirements

```bash
pip install playwright
playwright install chromium
```

---

## What to Look For

After each improvement:

**CQ scores**: Should stay ≥ 815 avg, ideally increase. If any drop below 700, investigate.

**Field completeness**: Must stay 5/5. Check: hook_text > 20 chars, ≥3 beats, scripts > 15 chars, full_script > 80 chars, CTA > 10 chars.

**Preflight time**: Should stay under 200s. If increasing, check Stage B concurrency.

**Generation time**: Should stay under 60s. If increasing, check Stage E parallelism.

**Validation passing**: After Improvement 4, all briefs should include `"validation_passed": true`.

**Signature phrases**: After Improvement 1, all briefs should include `"signature_phrases_used": [...]` with ≥2 phrases.

---

## Continuous Test Loop (for iterative improvement)

To run tests in a loop after changes:
```bash
while true; do
  python3 test_5creators.py 2>&1 | tee -a /tmp/bench_results.txt
  echo "--- Run complete at $(date) ---" | tee -a /tmp/bench_results.txt
  sleep 30
done
```

Or test a single creator repeatedly:
```bash
for i in {1..3}; do
  python3 test_5creators.py http://localhost:8000
  echo "--- Run $i complete ---"
done
```

---

## Production Deploy

```bash
cd /Users/mosaic/Downloads/magcontentinator_webapp
git add -A
git commit -m "improvement: [description]"
git push
```

Railway auto-deploys on push to main. Check logs at Railway dashboard. Allow ~2 min for deploy before re-running benchmark.

**Railway URL**: `https://stellar-youth-production.up.railway.app`

---

## Environment Variables

All secrets are in Railway environment (not .env file). For local testing, create `.env`:
```
OPENAI_API_KEY=...
APIFY_API_TOKEN=...
VIDEO_ANALYZER_URL=https://rl-video-analyzer-production-117b.up.railway.app
VIDEO_ANALYZER_KEY=...
```
