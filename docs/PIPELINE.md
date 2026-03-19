# Pipeline Architecture — All 6 Stages

## Overview

```
User input (handle)
    ↓
[A] Scraper ─────── Apify TikTok → top 10 videos + transcripts
    ↓
[B] Analyzer ─────── rl-video-analyzer (Gemini 2.5 Flash) → 37-field analysis per video
    ↓                 (fallback: GPT-4o transcript mode if user triggers skip)
[C] Profiler ─────── GPT-5.4 → archetype + identity + strengths/gaps
    ↓
[D] Voice ──────────  GPT-5.4 → tone, vocabulary, signature phrases, examples
    ↓
[LIB] Library ────── ashwamag_config.py → pain point + combo lookup for archetype group
[INSPO] Inspiration ─ GPT-4o-mini → digest of inspiration URLs/notes
    ↓ (user sets intent on Screen 2)
[E] Generator ──────  GPT-5.4 × 3 parallel brief generation + GPT-4o × 3 parallel CQ scoring
    ↓
3 briefs rendered (beat table + CQ score + regeneration loop)
```

---

## Stage A: Scraper (`stages/scraper.py`)

**Input**: TikTok handle
**Output**: `job["videos"]` = list of up to 10 video objects

- Calls Apify TikTok Scraper actor
- Fetches top 30, sorts by views, returns top 10
- Per-video data: video_id, url, views, likes, comments, shares, duration, cover_url, transcript, create_time
- Transcripts come from Apify's built-in extraction

**Key data quality note**: Transcripts are from Apify's ASR — quality varies. Good enough for voice fingerprinting, but not guaranteed complete.

---

## Stage B: Analyzer (`stages/analyzer.py`)

**Input**: `job["videos"]` (up to 10 videos)
**Output**: `job["analyzed_videos"]` = list of b1 analysis objects

**Primary path**: Calls `rl-video-analyzer` service (deployed at `https://rl-video-analyzer-production-117b.up.railway.app`)
- POST `/api/analyze` with video URL + custom prompt (`B1_VISUAL_PROMPT`)
- Poll `/api/status/{task_id}` every 3s until complete (max 3 min)
- 3 concurrent analyses via `asyncio.Semaphore(3)`
- Service uses Gemini 2.5 Flash to visually analyze the actual video

**Fallback path**: If user hits "skip" button (45s timeout), switches to GPT-4o transcript analysis

**Output schema** (37 fields per video):
```json
{
  "hook_type": "relatable_callout | authority_intro | ...",
  "hook_text": "first 3 seconds verbatim",
  "narrative_type": "problem_solution | transformation | ...",
  "pain_point": "sleep | stress | energy | ...",
  "archetype_signals": ["pharmacist", "authority_expert"],
  "signature_phrases": ["for real tho", "look here's the thing"],
  "transformation_proof": true/false,
  "social_proof": true/false,
  "product_first_appear_second": 15,
  "authority_level": 1-5,
  "clarity": 1-5,
  "beats": [{"time": "0-4s", "action": "...", "script": "...", "visual": "..."}],
  "full_transcript": "...",
  ...
}
```

**Known issue**: Stage C and D only use ~15 of these 37 fields — 60% of extracted data is discarded downstream.

---

## Stage C: Profiler (`stages/profiler.py`)

**Input**: `job["analyzed_videos"]` (all b1 analyses)
**Output**: `job["profile"]`

- Aggregates per-video data into counts: hook_types (Counter), narrative_types (Counter), pain_points (Counter)
- Calculates: transformation_proof_rate, social_proof_rate, avg_clarity, avg_authority
- Passes aggregated stats + hook_text snippets to GPT-5.4
- Outputs: archetype, archetype_confidence (0-1), secondary_archetypes, identity_constants, strengths[], gaps[]

**Identity constants extracted**: credential, setting, presentation_style, energy_level, audience_relationship

**Current weakness**: Archetype confidence is uncalibrated LLM output; identity is high-order inference from high-order inference (B1 infers archetype signals → C aggregates those inferences → GPT reasons from the aggregation).

---

## Stage D: Voice (`stages/voice.py`)

**Input**: `job["analyzed_videos"]` (top 5 by views) + `job["profile"]`
**Output**: `job["voice"]`

- Assembles transcripts from top 5 videos (tries: `full_transcript` → `transcript` → concatenate `beats[].script`)
- Truncates each to 2000 chars
- Passes transcripts + profile context to GPT-5.4

**Output schema** (9 dimensions):
```json
{
  "tone": "authoritative-but-approachable",
  "vocabulary": "medical_precision + conversational",
  "signature_phrases": ["look here's the thing", "for real tho", ...],  // 5 phrases
  "pace": "measured, pauses for emphasis",
  "hook_style": "skeptical_setup",
  "cta_style": "direct, links to personal credibility",
  "educational_style": "breaks down mechanism, no jargon without explanation",
  "authenticity_markers": ["mentions personal use", "self-deprecating humor"],
  "avoid": ["corporate language", "generic influencer tone"],
  "example_hook_in_their_voice": "Look, I've reviewed 50 sleep supplements...",
  "example_cta_in_their_voice": "Genuinely, go look at the beadlets..."
}
```

**Critical issue**: `example_hook_in_their_voice` and `example_cta_in_their_voice` are generated here but **never used in Stage E**. This is the biggest single quality gap.

---

## Library + Inspiration (`stages/library.py`, `stages/inspiration.py`)

**Library**: Reads `ashwamag_config.py` → looks up archetype group → returns top pain_point + combo for that group + GMV data
**Inspiration**: GPT-4o-mini digests any provided reference URLs/notes → adds creative direction context

---

## Stage E: Generator (`stages/generator.py`)

**Input**: All of the above (profile + voice + library_intel + inspiration_digest + user intent + strategy)
**Output**: `job["briefs"]` = 3 brief objects

**Generation**: GPT-5.4 × 3 briefs in parallel
- Brief 1: GMV Max
- Brief 2: Archetype Best
- Brief 3: Creator's Own

**Scoring**: GPT-4o × 3 CQ scores in parallel (immediately after generation)
- 10 dimensions, 46 sub-dimensions
- Returns: cq_total (/1000), cq_grade (A/B/C/D), per-dimension scores

**The system prompt** (`_build_system_prompt()`) assembles 10 sections:
1. Role + brief type context
2. Product formulation (from ashwamag_config.py)
3. Creator identity (profile)
4. Voice fingerprint (key-value list — but NOT including the examples)
5. Library intel (pain point + combo + GMV numbers)
6. Inspiration digest (if provided)
7. Compliance rules (banned angles, banned phrases, valid claims)
8. Strategy + intent (user input)
9. Chain-of-thought steps (5 reasoning steps before writing)
10. Output format (JSON schema)

**Chain-of-thought in system prompt**: Reasoning steps are in the system prompt, repeated for all 3 calls — wastes tokens and doesn't ground in per-brief context.

---

## Regen Loop

User can submit feedback on any brief → `POST /api/regen/{job_id}/{brief_num}`
- Re-runs Stage E for that single brief only
- Feedback injected into system prompt
- Other briefs preserved
- Results come via SSE `complete` event

---

## SSE Streaming

All progress is streamed via Server-Sent Events:
- `progress` — stage name + message (updates ribbon)
- `library_intel` — triggers library card render
- `preflight_complete` — archetype + videos analyzed
- `complete` — full brief payload
- `error` — error message

Queues: each connected client gets its own `asyncio.Queue`; pipeline emits to all queues via `job["_queues"]`.

---

## Benchmark Results (Current State)

From `test_5creators.py` run against production:
```
5/5 creators PASS
Avg preflight: 159s
Avg generation: 36s
Avg CQ: 815/1000 (grade B)
Videos analyzed: 10/10 for all creators
Field completeness: 5/5 for all creators
```

This is the baseline. Improvements should move avg CQ toward 850+ and improve brief-to-voice authenticity.
