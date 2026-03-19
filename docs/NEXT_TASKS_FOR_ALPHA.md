# ALPHA Next Tasks — Phase 4: Input Calibration + UX Sprint

> Written for ALPHA (Paperclip agent). Working dir: `/Users/mosaic/Downloads/magcontentinator_webapp/`
> Prod URL: `https://stellar-youth-production.up.railway.app`
> Read `STATUS.md` for what was done in the previous sprint. Read `REVIEW_BY_ALPHA.md` for architecture context.

---

## The Core Problem

User selections on the intent screen (Strategy, intent textarea) are **not actually routing different prompt behavior**. The `strategy` value is passed to the backend but only injected as a plain text label `"Strategy selection: sleep-score"`. No routing, no overrides, no special prompt sections.

The app looks like it does different things. It doesn't.

---

## Task 1 — Fix Sleep-Score Strategy (HIGHEST PRIORITY)

### What the user wants (brief directly from Pranav):

> **Theme**: Sleep before/after — show improvement on sleep scores as the visual proof backbone
> **Education**: Show that AshwaMag contains liposomal magnesium glycinate, which is the SUPERIOR version of regular magnesium glycinate because it's liposomal = better absorption

### Reference data (from `Custom_Sleep_Ideas_v2.xlsx` — validated set):
- Visual proof: WHOOP / Apple Watch / Fitbit / Oura sleep score screenshots
  - Before: 32-60% sleep score, red/yellow indicators, 4-6 hrs
  - After: 95-96% sleep score, green OPTIMAL, 8+ hrs, 98-99% recovery
- Liposomal rule (from V2 methodology): **analogy first → show beadlets → THEN name "liposomal"**
  - "Each beadlet wraps the magnesium in a fat layer → stomach acid breaks down regular mag glycinate, but can't break through fat → so the magnesium passes through intact → THAT is what liposomal means"
  - NEVER lead with "liposomal" — the word is unfamiliar; earn the name with the mechanism first
- Dominant combo for sleep: `before_after × problem_solution`
- Duration: 45-60s (sleep score reveal format is tighter than standard)

### What to implement:

**File**: `stages/generator.py` — add `STRATEGY_OVERRIDES` dict + routing in `_build_system_prompt()`

```python
STRATEGY_OVERRIDES = {
    "sleep-score": {
        "pain_point_override": "sleep",
        "combo_override": "before_after × problem_solution",
        "required_visual_proof": [
            "SLEEP SCORE REVEAL: Show sleep tracker screenshot (WHOOP/Apple Watch/Oura/Fitbit)",
            "BEFORE score: 32-60% sleep, red/yellow 'needs attention' indicators, 4-6 hrs recorded",
            "AFTER score: 95-96% sleep, green 'OPTIMAL' indicators, 8+ hrs, 98-99% recovery",
            "Beadlet close-up: show gummy with visible beadlets — this is the money shot",
        ],
        "required_education_section": """LIPOSOMAL EDUCATION — REQUIRED IN THIS BRIEF:
The brief MUST explain WHY AshwaMag's magnesium glycinate is superior to regular magnesium glycinate.
Teach it in this order (never skip or reorder):
1. ANALOGY: "Most magnesium glycinate breaks down in your stomach before your body can use it"
2. BEADLETS: "See these little beadlets inside the gummy? Each one wraps the magnesium in a fat layer"
3. MECHANISM: "Stomach acid breaks down regular magnesium, but it can't break through fat — so the magnesium passes through intact"
4. NAME IT: "That's what liposomal means — fat-wrapped delivery"
5. PROOF: "You can literally see the difference" (reference the visible beadlets)
NEVER lead with the word 'liposomal' — the mechanism earns the name.""",
        "hook_style_override": "before_after — open with the sleep score shock (the 'before' number)",
        "duration_target": "45-60s",
        "beat_structure_note": """SLEEP SCORE BRIEF STRUCTURE (follow this arc):
Beat 1 (0-4s): Show BEFORE sleep score — hook on the bad number ("Look at this — 38%")
Beat 2 (4-8s): Validate the struggle ("That's not even passing. I was waking up at 2, 3AM...")
Beat 3 (8-14s): Education hook ("Here's what I just found out. Not all mag glycinate is the same...")
Beat 4 (14-22s): Liposomal mechanism with beadlet demo (fat protection analogy → show beadlets → name it)
Beat 5 (22-28s): Reveal AFTER score ("Now look at this — 96%. Green. Optimal. 8 hours straight.")
Beat 6 (28-35s): CTA with urgency (specific, not just "link in bio")""",
    },
    "gmv-max": {
        # Library intel already handles this — just ensure the system knows to be explicit
        "system_note": "Prioritize the highest GMV pain point × combo for this archetype group. Be explicit in why_this_works about the GMV data backing this choice.",
    },
    "creators-best": {
        # Default behavior — no overrides needed, library intel handles it
        "system_note": "Lean into the creator's top-performing formats from their actual videos. Match the dominant combo from their video analysis.",
    },
    "custom": {
        # Intent textarea drives everything — skip library constraints
        "skip_library": True,
        "system_note": "The user's intent field is the primary driver. Ignore library combo suggestions. Build the brief around the angle described.",
    },
}
```

**In `_build_system_prompt()`**, after the library block, add strategy routing:
```python
# Strategy override block
strategy_overrides = STRATEGY_OVERRIDES.get(job.get("strategy", "creators-best"), {})
if strategy_overrides:
    override_lines = []

    if strategy_overrides.get("required_visual_proof"):
        override_lines.append("REQUIRED VISUAL PROOF (mandatory for this strategy):")
        for vp in strategy_overrides["required_visual_proof"]:
            override_lines.append(f"  - {vp}")

    if strategy_overrides.get("required_education_section"):
        override_lines.append(strategy_overrides["required_education_section"])

    if strategy_overrides.get("hook_style_override"):
        override_lines.append(f"HOOK STYLE REQUIRED: {strategy_overrides['hook_style_override']}")

    if strategy_overrides.get("beat_structure_note"):
        override_lines.append(strategy_overrides["beat_structure_note"])

    if strategy_overrides.get("system_note"):
        override_lines.append(f"STRATEGY NOTE: {strategy_overrides['system_note']}")

    strategy_override_block = "STRATEGY OVERRIDES — REQUIRED:\n" + "\n".join(override_lines) if override_lines else ""
else:
    strategy_override_block = ""
```

Also in `_build_user_prompt()`, add the pain_point_override to the user message:
```python
pain_override = STRATEGY_OVERRIDES.get(job.get("strategy",""), {}).get("pain_point_override")
if pain_override:
    lines += ["", f"REQUIRED PAIN POINT FOR THIS BRIEF: {pain_override} (strategy forces this — do not deviate)"]

combo_override = STRATEGY_OVERRIDES.get(job.get("strategy",""), {}).get("combo_override")
if combo_override:
    lines += ["", f"REQUIRED COMBO FOR THIS BRIEF: {combo_override} (strategy forces this — do not deviate)"]
```

Add `strategy_override_block` to the sections list in `_build_system_prompt()` — after `library_block`.

### Verify sleep-score works:
After implementing, test manually via the UI with @rphreviews + Sleep Score strategy selected.
Check: Does the brief contain a BEFORE/AFTER sleep score reveal? Does it explain liposomal via the beadlet mechanism? Does the hook open with a sleep score number?

---

## Task 2 — Fix Regen UX: Non-Blocking Regeneration

### The Problem
Current regen shows a full-screen blocking overlay:
```javascript
showOverlay('Regenerating brief 2…', 'Applying your feedback');
```
User can't read briefs 1 and 3 while brief 2 regenerates. This is the single biggest UX friction point after generation completes.

### Fix
**File**: `templates/index.html` — `regen()` function (line ~586) and `renderBriefRight()`

Replace the blocking overlay with a per-tab spinner:
```javascript
async function regen(briefIdx) {
  const ta = document.getElementById('rta' + (briefIdx + 1));
  const feedback = ta ? ta.value.trim() : '';
  const briefNum = briefIdx + 1;

  // Non-blocking: show spinner on this tab only, keep others accessible
  const tab = document.getElementById('tab' + briefNum);
  const origTabContent = tab ? tab.innerHTML : '';
  if (tab) tab.innerHTML = `<span class="tab-num">0${briefNum}</span><span class="skel-spin" style="display:inline-block;width:12px;height:12px;border-width:1.5px;vertical-align:middle;margin-left:4px"></span>`;

  // Show skeleton in this brief's left pane only
  const bl = document.getElementById('bl' + briefNum);
  if (bl) bl.innerHTML = `<div class="skel-wrap"><div class="skel-status"><div class="skel-spin"></div>Regenerating · applying feedback</div><div class="skel-line skel-title"></div><div class="skel-line skel-block"></div></div>`;

  try {
    await fetch(`/api/regen/${jobId}/${briefNum}`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({feedback})
    });
    // Result comes via SSE 'brief_ready' event — handled in connectSSE
  } catch(err) {
    if (tab) tab.innerHTML = origTabContent; // restore
    showToast('Regen failed: ' + err.message);
  }
}
```

Also update SSE handler for `brief_ready` event to handle regen completion (currently it only handles initial generation):
```javascript
eventSource.addEventListener('brief_ready', (e) => {
  const d = JSON.parse(e.data);
  if (d.regenerated && currentBriefs.length) {
    // Non-blocking regen completed — update just that brief
    const idx = d.brief_num - 1;
    // Fetch the updated job to get the full brief
    fetch(`/api/job/${jobId}`)
      .then(r => r.json())
      .then(job => {
        if (job.briefs && job.briefs[idx]) {
          currentBriefs[idx] = job.briefs[idx];
          renderBriefLeft(idx + 1, job.briefs[idx]);
          renderBriefRight(idx + 1, job.briefs[idx]);
          const tab = document.getElementById('tab' + (idx + 1));
          if (tab) {
            const hookShort = job.briefs[idx].hook_text ? job.briefs[idx].hook_text.substring(0, 35) + '…' : 'Brief ' + (idx + 1);
            tab.innerHTML = `<span class="tab-num">0${idx + 1}</span>${escHtml(hookShort)}`;
          }
          showToast('Brief ' + (idx + 1) + ' regenerated');
        }
      });
  }
});
```

---

## Task 3 — Fix Beat Time Field in Frontend Render

### The Problem
`renderBriefLeft()` uses `beat.time` (old field name, line ~633):
```javascript
<td class="t-time">${escHtml(beat.time || '')}</td>
```
But after Improvement 2, the schema uses `beat.time_range`. Time column is empty for all new briefs.

### Fix (one line)
In `renderBriefLeft()`:
```javascript
// Old:
<td class="t-time">${escHtml(beat.time || '')}</td>
// New:
<td class="t-time">${escHtml(beat.time_range || beat.time || '')}</td>
```

---

## Task 4 — Input Calibration Audit + Regen Prompt Improvement

### 4a: Verify intent textarea reaches generator
Trace: `intentTa` (frontend) → `intent` field in GenerateRequest → `job["intent"]` → `_build_user_prompt()` line `f"User strategy intent: {intent.strip()}"` → ✅ reaches model

Test: Enter "focus on sleep, gym setting, under 40s" → verify briefs reference gym setting and sleep

### 4b: Verify inspiration_note reaches generator
Trace: `inspoTa` → StartRequest → `create_job()` stores `inspiration_note` → `run_preflight()` calls inspiration stage → `job["inspiration_digest"]` → `_build_system_prompt()` injection → ✅ should reach model

Test: Enter inspiration note "Like how she explains beadlets simply" → verify briefs reference beadlet explanation style

### 4c: Improve regen feedback prompt
Current regen feedback is injected as:
```python
"REGENERATION FEEDBACK (previous version was rejected — fix these issues):",
feedback.strip(),
```

This is weak — the model doesn't know WHAT the previous brief was, so it can't specifically fix it.

**Fix**: Include the previous brief's hook_text and key gap in the regen prompt:
```python
if feedback.strip():
    # Get the previous version of this brief for context
    existing_briefs = job.get("briefs") or []
    brief_map = {b.get("brief_num"): b for b in existing_briefs}
    prev_brief = brief_map.get(regen_num, {})
    prev_hook = prev_brief.get("hook_text", "")

    lines += [
        "",
        "REGENERATION — previous version was rejected. Keep the same brief slot and strategy but fix these issues:",
        f"Previous hook was: \"{prev_hook}\"",
        f"User feedback: {feedback.strip()}",
        "Generate a meaningfully different version that directly addresses the feedback. Don't just rephrase.",
    ]
```

---

## Task 5 — UX Loading Experience During Preflight (150-180s wait)

### Current state
- User enters handle → goes to Screen 2
- Ribbon shows: "Starting analysis…" → steps A/B/C/D/LIB light up
- Steps are 5 dots — no detail on what's happening inside each stage
- 150-180s is a long time with minimal feedback

### Fix: Progressive status messages tied to SSE events
The `progress` events from the pipeline already emit stage-specific messages. They just need to be surfaced better.

**File**: `templates/index.html` — update the ribbon + add a sub-status area in Screen 2

Add a second line below the ribbon with more detailed status:
```html
<!-- Add to ribbon in S2 -->
<div id="ribbonDetail" style="font-size:11px;color:var(--ink4);margin-top:1px"></div>
```

Map stage names to human-readable messages in the SSE `progress` handler:
```javascript
const STAGE_LABELS = {
  'A': 'Fetching top videos…',
  'B': 'Analyzing video content with Gemini…',
  'C': 'Building creator profile…',
  'D': 'Fingerprinting creator voice…',
  'LIB': 'Matching library patterns…',
  'GEN': 'Generating briefs…',
  'E': 'Generating briefs…',
};

eventSource.addEventListener('progress', (e) => {
  const d = JSON.parse(e.data);
  updateRibbon(d.message);
  updateRibbonSteps(d.stage);
  const detail = document.getElementById('ribbonDetail');
  if (detail && STAGE_LABELS[d.stage]) detail.textContent = STAGE_LABELS[d.stage];
  // ... rest of handler
});
```

**Also**: During the ~150s wait, show the creator's handle prominently + a "why it takes time" explanation:
Add to Screen 2 body (below the intent form, visible while loading):
```html
<div id="analysisNote" style="font-size:11px;color:var(--ink4);text-align:center;line-height:1.8;padding:0 20px">
  Analyzing @<strong id="analysisHandle"></strong>'s top videos with Gemini AI.<br>
  This takes ~2-3 min — we're reading every video so the briefs actually sound like them.
</div>
```

---

## Task 6 — E2E Screenshot Test Loop (Playwright)

Run a full Playwright screenshot loop to document:
1. Screen 1 → Screen 2 → Screen 3 timing (with timestamps)
2. What the user sees at each stage (screenshots every 10s during preflight)
3. Regen flow: hit Regenerate on Brief 2, verify Brief 1 tab is still accessible
4. Sleep-score strategy: verify hook contains sleep score reveal + liposomal education

Test script: `test_e2e.py` exists, extend it or create `test_ux_loop.py`

Creators to test:
- @rphreviews (baseline, medical_authority)
- @bribez1 (ugc_authentic, hype energy)

Strategy to test for each:
- Default (creators-best)
- Sleep Score strategy (verify new routing works)
- Custom with intent "focus on liposomal beadlet education for pharmacists"

---

## Implementation Order

1. **Task 3** (beat time field fix — 1 line, instant)
2. **Task 1** (sleep-score strategy — highest priority, Pranav asked for this first)
3. **Task 2** (non-blocking regen — second biggest UX win)
4. **Task 4c** (regen prompt improvement — pairs with Task 2)
5. **Task 5** (loading UX — low risk, good polish)
6. **Task 4ab** (input audit — verification, not code change)
7. **Task 6** (screenshot test loop — validation)

---

## Commit Protocol

```bash
cd /Users/mosaic/Downloads/magcontentinator_webapp
git add <files>
git commit -m "fix: <description>

Co-Authored-By: Paperclip <noreply@paperclip.ing>"
```

After each commit: run `python3 test_5creators.py http://localhost:8000` or against prod after deploy.
Kill criterion: if any creator goes FAIL or field completeness drops below 5/5, revert.

---

## Success Criteria

- [ ] Sleep Score strategy briefs contain: before/after sleep score hook, liposomal education via beadlet mechanism, WHOOP/tracker screenshot visual proof requirement
- [ ] Regen is non-blocking (can read Brief 1 while Brief 2 regenerates)
- [ ] Beat time column shows time ranges in the brief table
- [ ] Regen feedback prompt includes previous hook for context
- [ ] Loading screen shows meaningful stage progress during 150s preflight
- [ ] E2E screenshot test documents full timing and flow
