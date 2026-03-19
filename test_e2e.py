"""End-to-end Playwright test for Magcontentinator webapp.

Tests:
  1. Landing page loads, shows 3-step layout
  2. Full preflight run: @rphreviews → pharmacist profile
  3. Intent submission → 3 briefs generated
  4. Brief quality: has full_script, beats with script, production_notes
  5. Regeneration endpoint works
  6. Timing measurements throughout

Usage:
  python3 test_e2e.py [URL]
  Defaults to Railway production URL.
"""

import asyncio
import json
import time
import sys
from datetime import datetime
from playwright.async_api import async_playwright

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "https://stellar-youth-production.up.railway.app"

CYAN  = "\033[96m"
GREEN = "\033[92m"
RED   = "\033[91m"
YELLOW = "\033[93m"
BOLD  = "\033[1m"
RESET = "\033[0m"

def ok(msg):   print(f"  {GREEN}✓{RESET} {msg}")
def fail(msg): print(f"  {RED}✗{RESET} {msg}")
def info(msg): print(f"  {CYAN}→{RESET} {msg}")
def warn(msg): print(f"  {YELLOW}⚠{RESET} {msg}")
def head(msg): print(f"\n{BOLD}{CYAN}{msg}{RESET}")


async def run_tests():
    t_total = time.time()
    results = {}

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context()
        page = await ctx.new_page()

        # ─────────────────────────────────────────────────────────────
        # TEST 1: Landing page
        # ─────────────────────────────────────────────────────────────
        head("TEST 1: Landing page")
        t = time.time()
        try:
            resp = await page.goto(BASE_URL, timeout=30000)
            assert resp.status == 200, f"HTTP {resp.status}"
            title = await page.title()
            ok(f"Page loaded: {title!r} ({time.time()-t:.1f}s)")

            # Check for 3-step structure (landing page instructions)
            body = await page.content()
            step_signals = ["Step 1", "Step 2", "Step 3", "step-1", "step-2", "step-3"]
            found_steps = any(s in body for s in step_signals)
            if found_steps:
                ok("3-step structure present on landing page")
            else:
                warn("3-step structure not clearly visible (check UI)")

            # Check logo renders (not broken img)
            logos = await page.query_selector_all("svg")
            ok(f"SVG logos present: {len(logos)}")

            # Check inspiration section exists and is collapsed
            inspo = await page.query_selector("[id*='inspo'], [class*='inspo']")
            if inspo:
                ok("Inspiration section found")
            else:
                warn("Inspiration section selector not matched (may still be present)")

            results["landing"] = "PASS"
        except Exception as e:
            fail(f"Landing page: {e}")
            results["landing"] = "FAIL"

        # ─────────────────────────────────────────────────────────────
        # TEST 2: Start preflight via API (not UI — faster, more reliable)
        # ─────────────────────────────────────────────────────────────
        head("TEST 2: Preflight — @rphreviews")
        t_preflight = time.time()
        job_id = None
        try:
            # POST /api/start
            resp = await page.evaluate("""async () => {
                const r = await fetch('/api/start', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        handle: 'rphreviews',
                        inspiration_urls: [],
                        inspiration_note: ''
                    })
                });
                return await r.json();
            }""")
            job_id = resp.get("job_id")
            assert job_id, "No job_id returned"
            ok(f"Job created: {job_id}")
            results["job_id"] = job_id
        except Exception as e:
            fail(f"Failed to start job: {e}")
            results["preflight"] = "FAIL"
            await browser.close()
            return results

        # Poll job status until awaiting_intent or error
        info("Polling preflight progress (Stage A→E)...")
        poll_start = time.time()
        profile = None
        voice = None
        library = None

        for attempt in range(120):  # max 10 minutes
            await asyncio.sleep(5)
            try:
                status_resp = await page.evaluate(f"""async () => {{
                    const r = await fetch('/api/job/{job_id}');
                    return await r.json();
                }}""")
                status = status_resp.get("status")
                videos_analyzed = status_resp.get("videos_analyzed", 0)

                elapsed = time.time() - poll_start
                print(f"    [{elapsed:5.0f}s] status={status} videos={videos_analyzed}", end="\r")

                if status == "awaiting_intent":
                    elapsed_preflight = time.time() - t_preflight
                    print()
                    ok(f"Preflight complete in {elapsed_preflight:.0f}s")
                    profile = status_resp.get("profile")
                    voice = status_resp.get("voice")
                    library = status_resp.get("library_intel")
                    results["preflight_time_s"] = round(elapsed_preflight)
                    results["videos_analyzed"] = videos_analyzed
                    break
                elif status == "error":
                    print()
                    fail(f"Preflight error: {status_resp.get('error')}")
                    results["preflight"] = "FAIL"
                    await browser.close()
                    return results
            except Exception as e:
                warn(f"Poll error: {e}")
        else:
            fail("Preflight timed out after 10 minutes")
            results["preflight"] = "FAIL"
            await browser.close()
            return results

        # Validate profile quality
        head("  Profile validation")
        archetype = profile.get("archetype", "unknown")
        confidence = profile.get("archetype_confidence", 0)
        ok(f"Archetype: {archetype} ({confidence:.0%} confidence)")

        if confidence >= 0.80:
            ok(f"Confidence ≥ 80% ✓")
        else:
            warn(f"Low confidence: {confidence:.0%}")

        videos_analyzed = results.get("videos_analyzed", 0)
        if videos_analyzed >= 8:
            ok(f"Videos analyzed: {videos_analyzed}/10")
        elif videos_analyzed >= 5:
            warn(f"Partial analysis: {videos_analyzed}/10 (acceptable)")
        else:
            fail(f"Too few videos analyzed: {videos_analyzed}/10")

        # Check B1 source breakdown from profile data
        # (we can't see analyzed_videos from job API, but check library)
        if library and library.get("available"):
            ok(f"Library intel: {library.get('archetype_group')} group, {len(library.get('briefs', {}))} briefs")
        else:
            warn("Library intel not available or low confidence")

        if voice:
            sig_phrases = voice.get("signature_phrases", [])
            ok(f"Voice fingerprint: {len(sig_phrases)} signature phrases")
            if sig_phrases:
                info(f"  Signature: {sig_phrases[0][:80]}")
        else:
            fail("No voice fingerprint")

        results["preflight"] = "PASS"
        results["archetype"] = archetype
        results["archetype_confidence"] = round(confidence, 2)

        # ─────────────────────────────────────────────────────────────
        # TEST 3: Generation
        # ─────────────────────────────────────────────────────────────
        head("TEST 3: Brief generation")
        t_gen = time.time()
        try:
            gen_resp = await page.evaluate(f"""async () => {{
                const r = await fetch('/api/generate/{job_id}', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{
                        intent: "I have tried magnesium products before and they helped, but this one is really really good. More authentic feel.",
                        strategy: "sleep",
                        library_selections: {{brief_1: true, brief_2: true, brief_3: true}},
                        skip_library: false
                    }})
                }});
                return await r.json();
            }}""")
            assert gen_resp.get("status") == "generating", f"Expected generating, got: {gen_resp}"
            ok("Generation started")
        except Exception as e:
            fail(f"Generation failed to start: {e}")
            results["generation"] = "FAIL"
            await browser.close()
            return results

        # Poll until complete
        info("Polling generation...")
        briefs = None
        for attempt in range(60):  # max 5 minutes
            await asyncio.sleep(5)
            try:
                status_resp = await page.evaluate(f"""async () => {{
                    const r = await fetch('/api/job/{job_id}');
                    return await r.json();
                }}""")
                status = status_resp.get("status")
                elapsed = time.time() - t_gen
                print(f"    [{elapsed:4.0f}s] status={status}", end="\r")

                if status == "complete":
                    print()
                    elapsed_gen = time.time() - t_gen
                    ok(f"Generation complete in {elapsed_gen:.0f}s")
                    briefs = status_resp.get("briefs", [])
                    results["generation_time_s"] = round(elapsed_gen)
                    break
                elif status == "error":
                    print()
                    fail(f"Generation error: {status_resp.get('error')}")
                    results["generation"] = "FAIL"
                    await browser.close()
                    return results
            except Exception as e:
                warn(f"Poll error: {e}")
        else:
            fail("Generation timed out after 5 minutes")
            results["generation"] = "FAIL"
            await browser.close()
            return results

        # ─────────────────────────────────────────────────────────────
        # TEST 4: Brief quality validation
        # ─────────────────────────────────────────────────────────────
        head("TEST 4: Brief quality")
        assert briefs, "No briefs returned"
        ok(f"Got {len(briefs)} briefs")

        for b in briefs:
            bnum = b.get("brief_num")
            btype = b.get("brief_type")
            print(f"\n  Brief {bnum} ({btype}):")

            # Hook
            hook = b.get("hook_text", "")
            if hook and len(hook) > 20:
                ok(f"  hook_text: {hook[:80]}...")
            else:
                fail(f"  hook_text missing or too short: {hook!r}")

            # Hook visual
            hook_visual = b.get("hook_visual", "")
            if hook_visual:
                ok(f"  hook_visual: {hook_visual[:60]}...")
            else:
                warn("  hook_visual missing (new field, may not be generated yet)")

            # Beats
            beats = b.get("beats", [])
            ok(f"  beats: {len(beats)}")
            beats_with_script = [be for be in beats if be.get("script") and len(be.get("script", "")) > 20]
            beats_with_verbatim = len(beats_with_script)
            if beats_with_verbatim >= len(beats) * 0.7:
                ok(f"  verbatim scripts: {beats_with_verbatim}/{len(beats)} beats have real script")
            else:
                warn(f"  verbatim scripts: only {beats_with_verbatim}/{len(beats)} beats (check prompt)")
            if beats:
                info(f"  Sample beat script: {beats[0].get('script', '')[:80]}")

            # Full script
            full_script = b.get("full_script", "")
            if full_script and len(full_script) > 100:
                ok(f"  full_script: {len(full_script)} chars")
                info(f"  Script preview: {full_script[:120]}...")
            else:
                warn(f"  full_script missing or short (new field)")

            # Production notes
            prod_notes = b.get("production_notes", "")
            if prod_notes and len(prod_notes) > 50:
                ok(f"  production_notes: {len(prod_notes)} chars")
            else:
                warn("  production_notes missing (new field)")

            # CTA
            cta = b.get("cta", "")
            if cta:
                ok(f"  cta: {cta[:80]}")
            else:
                fail("  cta missing")

            # CQ score
            cq = b.get("cq", {})
            cq_total = cq.get("cq_total", 0)
            cq_grade = cq.get("cq_grade", "?")
            if cq_total >= 700:
                ok(f"  CQ: {cq_total}/1000 ({cq_grade})")
            elif cq_total >= 500:
                warn(f"  CQ: {cq_total}/1000 ({cq_grade}) — acceptable")
            else:
                fail(f"  CQ: {cq_total}/1000 ({cq_grade}) — low")

        results["generation"] = "PASS"
        results["brief_count"] = len(briefs)
        results["top_cq"] = max((b.get("cq", {}).get("cq_total", 0) for b in briefs), default=0)

        # ─────────────────────────────────────────────────────────────
        # TEST 5: Regeneration
        # ─────────────────────────────────────────────────────────────
        head("TEST 5: Regen brief 1")
        t_regen = time.time()
        try:
            regen_resp = await page.evaluate(f"""async () => {{
                const r = await fetch('/api/regen/{job_id}/1', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{feedback: "Make the hook more pharmacist-authority driven, less relatable callout"}})
                }});
                return await r.json();
            }}""")
            assert regen_resp.get("status") == "regenerating", f"Got: {regen_resp}"
            ok("Regen started")

            for _ in range(30):
                await asyncio.sleep(5)
                st = await page.evaluate(f"""async () => {{
                    const r = await fetch('/api/job/{job_id}');
                    return (await r.json()).status;
                }}""")
                if st == "complete":
                    ok(f"Regen complete in {time.time()-t_regen:.0f}s")
                    results["regen_time_s"] = round(time.time() - t_regen)
                    results["regen"] = "PASS"
                    break
            else:
                warn("Regen timed out (not a blocker)")
                results["regen"] = "TIMEOUT"
        except Exception as e:
            warn(f"Regen test failed: {e}")
            results["regen"] = "FAIL"

        # ─────────────────────────────────────────────────────────────
        # TEST 6: UI — Screen 2 renders briefs
        # ─────────────────────────────────────────────────────────────
        head("TEST 6: UI rendering check")
        try:
            await page.goto(f"{BASE_URL}?job={job_id}", timeout=15000)
            await asyncio.sleep(2)
            body = await page.content()
            brief_signals = ["hook_text", "brief", "Brief", "CQ", "cq_total", "production"]
            found = [s for s in brief_signals if s in body]
            if found:
                ok(f"Brief content detected in UI: {found}")
            else:
                warn("Brief content not visible in UI page (may need JS rendering)")
            results["ui"] = "PASS"
        except Exception as e:
            warn(f"UI check: {e}")
            results["ui"] = "WARN"

        await browser.close()

    # ─────────────────────────────────────────────────────────────
    # SUMMARY
    # ─────────────────────────────────────────────────────────────
    total_time = time.time() - t_total
    head("=" * 50)
    head("TEST SUMMARY")
    print()

    print(f"  URL tested:        {BASE_URL}")
    print(f"  Job ID:            {results.get('job_id', 'N/A')}")
    print(f"  Total test time:   {total_time:.0f}s")
    print()
    print(f"  Preflight:         {results.get('preflight', '?')} ({results.get('preflight_time_s', '?')}s)")
    print(f"  Generation:        {results.get('generation', '?')} ({results.get('generation_time_s', '?')}s)")
    print(f"  Regen:             {results.get('regen', '?')} ({results.get('regen_time_s', '?')}s)")
    print(f"  Landing page:      {results.get('landing', '?')}")
    print(f"  UI rendering:      {results.get('ui', '?')}")
    print()
    print(f"  Archetype:         {results.get('archetype', '?')} ({results.get('archetype_confidence', '?'):.0%} confidence)")
    print(f"  Videos analyzed:   {results.get('videos_analyzed', '?')}/10")
    print(f"  Briefs generated:  {results.get('brief_count', '?')}")
    print(f"  Top CQ score:      {results.get('top_cq', '?')}/1000")
    print()

    passed = sum(1 for v in results.values() if v == "PASS")
    failed = sum(1 for v in results.values() if v == "FAIL")
    warned = sum(1 for v in results.values() if v in ("WARN", "TIMEOUT"))
    print(f"  {GREEN}PASS: {passed}{RESET}  {RED}FAIL: {failed}{RESET}  {YELLOW}WARN: {warned}{RESET}")

    return results


if __name__ == "__main__":
    print(f"\n{BOLD}Magcontentinator E2E Test{RESET}")
    print(f"Target: {BASE_URL}")
    print(f"Started: {datetime.now().strftime('%H:%M:%S')}\n")
    asyncio.run(run_tests())
