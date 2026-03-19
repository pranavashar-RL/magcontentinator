"""AshwaMag Gummies — all product intelligence baked in. Single source of truth for all prompts."""

PRODUCT_NAME = "AshwaMag Gummies"
BRAND = "Rootlabs"
TAGLINE = "10-in-1 Magnesium Complex with KSM-66 Ashwagandha"
TARGET_AUDIENCE = "Women (primary)"

FORMULATION = """
PRODUCT: AshwaMag Gummies by Rootlabs
FORMAT: Gummy with visible beadlets inside
TAGLINE: 10-in-1 Magnesium Complex with KSM-66 Ashwagandha

MAGNESIUM: 10 forms, 675mg total compound, 168mg elemental
- Key forms: glycinate, malate, taurate, liposomal
- Delivery: Beadlet technology inside gummy — protected until absorption (visual proof: you can SEE the beadlets)
- 5x absorption vs regular magnesium oxide
- Supports both passive (80-90%) and active (10-20%) absorption pathways

ASHWAGANDHA: KSM-66, 200mg — clinically studied adaptogen for stress modulation
L-THEANINE: 26mg — equivalent to 1-2 cups green tea, supports relaxation without drowsiness

KEY DIFFERENTIATORS:
1. Beadlet technology — you can SEE the beadlets (visual proof of delivery)
2. First gummy to deploy beadlet technology at scale — delivery standards of advanced capsules
3. 5x absorption claim (science-backed)
4. Liposomal magnesium improves intestinal uptake
5. Third-party lab tested (COA available)
6. Non-GMO, no artificial dyes
7. One gummy replaces multiple supplement bottles
"""

VALID_CLAIMS = [
    "Supports stress recovery",
    "Supports sleep quality",
    "Supports relaxation and calm",
    "Supports muscle recovery",
    "Supports cognitive function and mental clarity",
    "Supports daily magnesium needs",
    "10 magnesium forms delivered via protected beadlets",
    "675mg total magnesium compounds, 168mg elemental magnesium",
    "Beadlet technology protects actives until absorption",
    "Liposomal magnesium improves intestinal uptake and gut tolerance",
    "KSM-66 ashwagandha — clinically studied adaptogen",
    "L-theanine supports relaxation",
    "Third-party lab tested (COA available)",
    "Non-GMO, no artificial dyes",
]

INVALID_CLAIMS = [
    "Cures or treats any disease",
    "Cures anxiety or depression",
    "Replaces medication (benzos, SSRIs, sleep aids)",
    "Clinically proven to treat insomnia",
    "FDA approved",
    "Will definitely help you sleep",
    "Eliminates stress",
    "Fixes hormonal imbalance",
    "Burns belly fat or cortisol face",
    "Replaces your doctor",
]

# HARD BANNED — never generate content using these angles
BANNED_ANGLES = {"anxiety_treatment", "weight_loss", "body_shaming", "weight_body_comp"}
BANNED_PHRASES = [
    "if your cooch looks like this",
    "cures anxiety",
    "lose weight",
    "belly fat",
    "moon face cure",
    "cortisol face",
    "fat burning",
    "appetite suppression",
    "body composition",
]
BANNED_VISUALS = [
    "Before/after body transformation implying weight loss",
    "Medical diagnosis imagery",
    "Prescription medication comparison",
]

# Pain points ranked by GMV (BANNED ones excluded)
PAIN_POINTS = {
    "sleep": {
        "total_gmv": 593277,
        "n_videos": 58,
        "avg_gmv": 10229,
        "key_ingredients": ["magnesium glycinate", "L-theanine", "KSM-66 ashwagandha"],
        "claims": [
            "Magnesium glycinate supports sleep onset and quality",
            "L-theanine promotes relaxation without drowsiness",
            "KSM-66 ashwagandha supports stress recovery that disrupts sleep",
            "Beadlet delivery protects magnesium through digestion for better absorption",
        ],
        "hooks_that_convert": [
            "pharmacist warns about sleep aids",
            "brain won't shut off at 2AM",
            "80% of people are deficient",
        ],
        "visual_proof": ["Show gummy texture with visible beadlets", "COA/lab results", "sleep tracker screenshot"],
    },
    "brain_fog": {
        "total_gmv": 357737,
        "n_videos": 20,
        "avg_gmv": 17887,
        "key_ingredients": ["magnesium", "L-theanine", "KSM-66 ashwagandha"],
        "claims": [
            "Magnesium supports cognitive function and mental clarity",
            "L-theanine promotes focused calm",
            "Multiple magnesium forms support neurological function",
            "Beadlet technology ensures better delivery to where it matters",
        ],
        "hooks_that_convert": [
            "can't focus on anything",
            "brain fog is not normal",
            "80% are deficient in this",
        ],
        "visual_proof": ["Focus/productivity before-after", "Ingredient label zoom", "Beadlet close-up"],
    },
    "stress_cortisol": {
        "total_gmv": 268428,
        "n_videos": 67,
        "avg_gmv": 4006,
        "key_ingredients": ["KSM-66 ashwagandha", "magnesium", "L-theanine"],
        "claims": [
            "KSM-66 ashwagandha is clinically studied for stress modulation",
            "Magnesium supports HPA axis function",
            "L-theanine equivalent to 1-2 cups green tea for calm",
            "Adaptogenic support for daily stress recovery",
        ],
        "hooks_that_convert": [
            "cortisol levels through the roof",
            "burnout is not normal",
            "running on empty",
        ],
        "visual_proof": ["Mood journal entries", "COA", "Stress before/after tracker"],
    },
    "low_energy": {
        "total_gmv": 169930,
        "n_videos": 23,
        "avg_gmv": 7388,
        "key_ingredients": ["magnesium malate", "KSM-66 ashwagandha", "multi-form magnesium"],
        "claims": [
            "Magnesium supports energy production at the cellular level",
            "KSM-66 ashwagandha supports sustained energy without stimulants",
            "Magnesium malate is specifically linked to energy metabolism",
            "Addressing deficiency restores natural energy levels",
        ],
        "hooks_that_convert": [
            "exhausted by 2PM",
            "tired of being tired",
            "blue-collar worker needs this",
        ],
        "visual_proof": ["Energy level comparison", "Day-in-the-life context", "No caffeine needed"],
    },
    "muscle_recovery": {
        "total_gmv": 120000,
        "n_videos": 15,
        "avg_gmv": 8000,
        "key_ingredients": ["magnesium malate", "magnesium taurate", "magnesium glycinate"],
        "claims": [
            "Multiple magnesium forms support muscle function and recovery",
            "Magnesium malate specifically supports muscle energy production",
            "Magnesium taurate supports cardiovascular and muscle function",
            "Better absorption means more magnesium reaches muscles",
        ],
        "hooks_that_convert": [
            "cramps at 3AM",
            "restless legs ruining sleep",
            "gym recovery hack",
        ],
        "visual_proof": ["Workout context", "Leg cramp demonstration", "Label showing forms"],
    },
    "pms_hormones": {
        "total_gmv": 95000,
        "n_videos": 12,
        "avg_gmv": 7917,
        "key_ingredients": ["magnesium glycinate", "KSM-66 ashwagandha", "L-theanine"],
        "claims": [
            "Magnesium supports menstrual comfort",
            "KSM-66 ashwagandha supports hormonal balance",
            "Magnesium glycinate is gentle on the stomach",
            "Daily use supports consistent mineral levels through the cycle",
        ],
        "hooks_that_convert": [
            "PMS cramps every month",
            "period week survival",
            "hormones are out of control",
        ],
        "visual_proof": ["Period tracking app", "Relatable cramping reenactment", "Gummy consumption ritual"],
    },
    "general_wellness": {
        "total_gmv": 85000,
        "n_videos": 30,
        "avg_gmv": 2833,
        "key_ingredients": ["10-form magnesium complex", "KSM-66 ashwagandha", "L-theanine"],
        "claims": [
            "80% of people are magnesium deficient",
            "10 forms cover multiple magnesium pathways",
            "One gummy simplifies your supplement stack",
            "Beadlet technology makes this the most advanced gummy on the market",
        ],
        "hooks_that_convert": [
            "stop taking the wrong magnesium",
            "supplement companies don't want you to know",
            "pharmacist's #1 recommendation",
        ],
        "visual_proof": ["Beadlet close-up", "Ingredient comparison vs competitors", "COA/lab results"],
    },
}

# Combos ranked by GMV (hook × narrative)
TOP_COMBOS = [
    {"hook": "relatable_callout", "narrative": "problem_solution", "total_gmv": 580390, "n_videos": 112, "avg_gmv": 5182},
    {"hook": "bold_claim", "narrative": "problem_solution", "total_gmv": 117891, "n_videos": 24, "avg_gmv": 4912},
    {"hook": "controversial_take", "narrative": "problem_solution", "total_gmv": 115311, "n_videos": 6, "avg_gmv": 19219},
    {"hook": "before_after", "narrative": "problem_solution", "total_gmv": 126060, "n_videos": 9, "avg_gmv": 14007},
    {"hook": "negative_framing", "narrative": "problem_solution", "total_gmv": 81802, "n_videos": 18, "avg_gmv": 4545},
    {"hook": "personal_story", "narrative": "problem_solution", "total_gmv": 48237, "n_videos": 10, "avg_gmv": 4824},
    {"hook": "authority_intro", "narrative": "problem_solution", "total_gmv": 40239, "n_videos": 7, "avg_gmv": 5748},
    {"hook": "social_proof_callout", "narrative": "problem_solution", "total_gmv": 40062, "n_videos": 4, "avg_gmv": 10016},
    {"hook": "personal_story", "narrative": "testimonial", "total_gmv": 38990, "n_videos": 5, "avg_gmv": 7798},
    {"hook": "bold_claim", "narrative": "testimonial", "total_gmv": 36378, "n_videos": 9, "avg_gmv": 4042},
]

# Archetype groups (from Magcontentinator_v2/brief_builder.py)
ARCHETYPE_GROUPS = {
    "medical_authority": ["pharmacist", "nurse", "health_educator", "nutrition_coach", "doctor"],
    "wellness_lifestyle": ["wellness_influencer", "mom_lifestyle", "beauty_guru", "lifestyle"],
    "fitness": ["fitness_influencer", "fitness_coach", "athlete"],
    "direct_commerce": ["deal_hunter", "deal_announcer", "product_reviewer", "tiktok_shop_affiliate"],
    "ugc_authentic": ["ugc_creator", "everyday_consumer", "authentic_testimonial_giver"],
    "blue_collar_rural": ["blue_collar_worker_persona", "rural_lifestyle_influencer", "fatherly_advisor"],
    "reaction_story": ["reaction_creator", "relatable_storyteller"],
}

# Archetype group → best pain points (ordered by archetype-specific GMV performance)
ARCHETYPE_PAIN_POINTS = {
    "medical_authority": ["brain_fog", "sleep", "general_wellness", "stress_cortisol", "muscle_recovery"],
    "wellness_lifestyle": ["sleep", "stress_cortisol", "pms_hormones", "low_energy", "brain_fog"],
    "fitness": ["muscle_recovery", "low_energy", "sleep", "brain_fog", "stress_cortisol"],
    "direct_commerce": ["sleep", "general_wellness", "low_energy", "brain_fog", "stress_cortisol"],
    "ugc_authentic": ["sleep", "stress_cortisol", "low_energy", "pms_hormones", "brain_fog"],
    "blue_collar_rural": ["low_energy", "muscle_recovery", "sleep", "stress_cortisol", "brain_fog"],
    "reaction_story": ["sleep", "brain_fog", "low_energy", "stress_cortisol", "pms_hormones"],
}

# Archetype group → best combos (ordered by archetype-specific performance)
ARCHETYPE_COMBOS = {
    "medical_authority": ["controversial_take × problem_solution", "bold_claim × problem_solution", "authority_intro × problem_solution"],
    "wellness_lifestyle": ["relatable_callout × problem_solution", "before_after × problem_solution", "personal_story × testimonial"],
    "fitness": ["bold_claim × problem_solution", "before_after × problem_solution", "relatable_callout × problem_solution"],
    "direct_commerce": ["relatable_callout × problem_solution", "social_proof_callout × problem_solution", "bold_claim × testimonial"],
    "ugc_authentic": ["relatable_callout × problem_solution", "personal_story × testimonial", "personal_story × problem_solution"],
    "blue_collar_rural": ["relatable_callout × problem_solution", "personal_story × problem_solution", "bold_claim × problem_solution"],
    "reaction_story": ["relatable_callout × problem_solution", "personal_story × testimonial", "negative_framing × problem_solution"],
}

CONTENT_STRATEGY_RULES = """
CONTENT STRATEGY RULES (data-validated from $1.73M GMV library):

1. DURATION: 60+ seconds outperform shorter. Never suggest a video under 55 seconds.
2. AUTHORITY PREMIUM: Authority/expert hooks convert at 28x higher GMV/video vs relatable hooks alone.
   Always position authority creators (pharmacist, nurse, nutrition coach) with credential-first hooks.
3. TRANSFORMATION GAP: Transformation proof (before/after, tracker screenshots, lab results) appears in
   83% of competitor videos but only 8% of AshwaMag videos. ALWAYS include a transformation proof element.
4. SOCIAL PROOF GAP: 19% AshwaMag vs 37% competitors mention reviews/testimonials.
   Always include one social proof line in the video (reviews, units sold, community).
5. COA/LAB TESTING: Appears in 73% of GMV videos. Make it standard — include as PIP insert or verbal callout.
6. LIPOSOMAL MESSAGING: Never lead with 'liposomal'. Lead with analogy → show beadlets → THEN name it.
7. CTA REQUIREMENTS: Every video needs urgency ('limited batch', 'selling out') + specific offer.
8. DOMINANT COMBO: relatable_callout × problem_solution = $580K GMV across 112 videos. The default.
"""

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


def get_archetype_group(archetype: str) -> str:
    """Map a creator archetype to its group."""
    archetype_lower = archetype.lower().replace(" ", "_")
    for group, members in ARCHETYPE_GROUPS.items():
        if archetype_lower in members or archetype_lower == group:
            return group
    return "ugc_authentic"  # default

def get_library_intel(archetype: str, brief_num: int = 1) -> dict:
    """Get library intelligence for a given archetype and brief slot."""
    group = get_archetype_group(archetype)
    pain_points = ARCHETYPE_PAIN_POINTS.get(group, ARCHETYPE_PAIN_POINTS["ugc_authentic"])
    combos = ARCHETYPE_COMBOS.get(group, ARCHETYPE_COMBOS["ugc_authentic"])

    # brief_num 1=GMV max, 2=archetype best, 3=creator's own best
    pain_idx = min(brief_num - 1, len(pain_points) - 1)
    combo_idx = min(brief_num - 1, len(combos) - 1)

    pain_key = pain_points[pain_idx]
    combo = combos[combo_idx]
    pain_data = PAIN_POINTS.get(pain_key, PAIN_POINTS["general_wellness"])

    # Parse combo
    parts = combo.split(" × ")
    hook = parts[0] if len(parts) > 0 else "relatable_callout"
    narrative = parts[1] if len(parts) > 1 else "problem_solution"

    # Find combo GMV
    combo_gmv = 0
    for c in TOP_COMBOS:
        if c["hook"] == hook and c["narrative"] == narrative:
            combo_gmv = c["total_gmv"]
            break

    return {
        "archetype_group": group,
        "pain_point": pain_key,
        "pain_point_data": pain_data,
        "combo": combo,
        "hook": hook,
        "narrative": narrative,
        "combo_gmv": combo_gmv,
        "pain_total_gmv": pain_data["total_gmv"],
        "pain_avg_gmv": pain_data["avg_gmv"],
    }

def build_library_context(archetype: str, brief_num: int = 1) -> str:
    """Build a library context string for injection into system prompts."""
    intel = get_library_intel(archetype, brief_num)
    pain = intel["pain_point_data"]
    pain_key = intel["pain_point"]
    combo = intel["combo"]

    base = f"""LIBRARY INTELLIGENCE (from $1.73M GMV validated dataset):

BRIEF {brief_num} ASSIGNMENT:
- Pain Point: {pain_key.replace("_", " ").title()} (${intel["pain_total_gmv"]:,} total GMV, {pain["n_videos"]} videos, ${intel["pain_avg_gmv"]:,} avg)
- Combo: {combo} (${intel["combo_gmv"]:,} total GMV)
- Archetype Group: {intel["archetype_group"].replace("_", " ").title()}

KEY INGREDIENTS FOR THIS PAIN POINT:
{chr(10).join(f"- {ing}" for ing in pain["key_ingredients"])}

PROVEN CLAIMS:
{chr(10).join(f"- {claim}" for claim in pain["claims"])}

HOOKS THAT CONVERT:
{chr(10).join(f"- {hook}" for hook in pain["hooks_that_convert"])}

VISUAL PROOF ELEMENTS (use at least one):
{chr(10).join(f"- {v}" for v in pain["visual_proof"])}"""

    # Improvement 5: inject rationale for why this pain point + combo converts
    pain_rationale = LIBRARY_RATIONALE.get(pain_key, {})
    if pain_rationale:
        base += f"\n\nWHY THIS PAIN POINT CONVERTS: {pain_rationale.get('why_it_converts', '')}"
        anti = pain_rationale.get("anti_patterns", [])
        if anti:
            base += f"\nAVOID THESE PATTERNS: {', '.join(anti)}"

    combo_rationale = COMBO_RATIONALE.get(combo, {})
    if combo_rationale:
        base += f"\n\nWHY THIS COMBO WORKS: {combo_rationale.get('why', '')}"
        exec_note = combo_rationale.get("execution_note", "")
        if exec_note:
            base += f"\nEXECUTION NOTE: {exec_note}"
        what_not = combo_rationale.get("what_not_to_do", "")
        if what_not:
            base += f"\nDO NOT: {what_not}"

    return base.strip()
