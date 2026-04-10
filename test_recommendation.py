"""
test_recommendation.py — Full test suite for the True Grind recommendation system.

Run:  python3 test_recommendation.py

Tests:
  Part A: Taste note parser (keyword mode)
  Part B: Initial grind classification messages
  Part C: Recommendation engine — all logic paths with brew variables
"""

import json
from recommendation.recommendation_engine import recommend_filter, classify_grind_message
from recommendation.taste_parser import parse_taste_notes

# ── PART A: Taste Note Parser ────────────────────────────

print("=" * 60)
print("PART A: Taste Note Parser (keyword mode)")
print("=" * 60)

test_notes = [
    ("It was too bitter and muddy, with a heavy body", ["bitter", "heavy", "muddy"]),
    ("Sour and thin, kind of hollow tasting", ["hollow", "sour", "thin"]),
    ("Really well balanced, sweet chocolate notes", ["balanced", "chocolatey", "sweet"]),
    ("It tasted both sour and bitter", ["bitter", "sour", "sour_and_bitter"]),
    ("Pretty good, smooth and clean", ["clean", "good", "smooth"]),
    ("Harsh and dry, almost burnt", ["burnt", "dry", "harsh"]),
    ("watery and weak, not much flavor", ["thin", "weak"]),
]

all_pass = True
for note, expected in test_notes:
    tags = parse_taste_notes(note, use_llm=False)
    status = "✅" if all(e in tags for e in expected) else "⚠️"
    if status == "⚠️":
        all_pass = False
    print(f"  {status} \"{note}\"")
    print(f"     → {tags}")

print(f"\n{'✅ All parser tests passed' if all_pass else '⚠️ Some parser tests need review'}\n")


# ── PART B: Grind Classification Messages ────────────────

print("=" * 60)
print("PART B: Initial Grind Classification Messages")
print("=" * 60)

classification_tests = [
    (620, "pour_over", "well-suited"),
    (400, "pour_over", "finer than ideal"),
    (800, "pour_over", "coarser than ideal"),
    (800, "french_press", "well-suited"),
    (450, "moka_pot", "well-suited"),
    (600, "aeropress", "coarser than ideal"),
]

for d50, method, expected_phrase in classification_tests:
    msg = classify_grind_message(d50, brew_method=method)
    status = "✅" if expected_phrase in msg else "❌"
    print(f"  {status} D50={d50}µm, method={method}")
    print(f"     → {msg}")

print()


# ── PART C: Full Recommendation Engine ───────────────────

print("=" * 60)
print("PART C: Recommendation Engine (with brew variables)")
print("=" * 60)

BASE = {
    "current_setting": 5,        # Fellow Ode setting
    "fitted_slope": 50,          # Fellow Ode has large steps
    "dial_range_min": 1,
    "dial_range_max": 11,
}

GOOD_DIST = {
    "fines_pct": 4.0, "uniform_pct": 88.5, "boulders_pct": 1.2,
    "bimodal_flag": False, "uniformity": "good", "span": 0.8,
}

BIMODAL_DIST = {
    "fines_pct": 22.0, "uniform_pct": 55.0, "boulders_pct": 18.0,
    "bimodal_flag": True, "uniformity": "poor", "span": 2.1,
}

POOR_DIST = {
    "fines_pct": 12.0, "uniform_pct": 62.0, "boulders_pct": 5.0,
    "bimodal_flag": False, "uniformity": "poor", "span": 1.8,
}


def run_test(name: str, overrides: dict):
    payload = {**BASE, **overrides}
    result = recommend_filter(payload)
    grind = result["grind_recommendation"]
    secondary = result["secondary_advice"]
    brew = result.get("brew_analysis", {})

    print(f"\n{'─'*55}")
    print(f"TEST: {name}")
    print(f"  D50:           {payload['current_d50']} µm")
    print(f"  Brew method:   {result.get('brew_method', 'n/a')}")
    print(f"  Taste:         {payload['taste_feedback']}")
    print(f"  Mode:          {result['mode']}")
    print(f"  Grind:         {grind['direction']} {grind['steps']} steps → setting {grind['to_setting']}")
    print(f"  Message:       {grind['message'][:100]}")
    if secondary["shown"]:
        print(f"  Secondary:     {secondary['type']} → {secondary['direction']}")
        print(f"  Sec. message:  {secondary['message'][:100]}")
    brew_issues = brew.get("issues", [])
    if brew_issues:
        print(f"  Brew issues:   {len(brew_issues)}")
        for issue in brew_issues:
            print(f"    ⚠️ {issue[:90]}")


# Test 1: Too coarse for pour-over
run_test("Too coarse for pour-over → go finer", {
    "current_d50": 750,
    "taste_feedback": ["sour", "thin"],
    "psd_stats": GOOD_DIST,
    "brew_method": "pour_over",
    "water_temp_c": 94,
    "extraction_time_s": 200,
    "filter_type": "paper",
    "dose_g": 20,
    "water_g": 320,
})

# Test 2: Good grind for French press
run_test("Good grind for French press → hold", {
    "current_d50": 800,
    "taste_feedback": ["balanced", "rich"],
    "psd_stats": GOOD_DIST,
    "brew_method": "french_press",
    "water_temp_c": 95,
    "extraction_time_s": 270,
    "dose_g": 30,
    "water_g": 500,
})

# Test 3: Sour with low water temp
run_test("Near target + sour + low temp → raise temp", {
    "current_d50": 610,
    "taste_feedback": ["sour"],
    "psd_stats": GOOD_DIST,
    "brew_method": "pour_over",
    "water_temp_c": 85,
    "extraction_time_s": 200,
    "filter_type": "paper",
    "dose_g": 20,
    "water_g": 320,
})

# Test 4: Bitter with long extraction
run_test("Near target + bitter + long extraction → needs adjustment", {
    "current_d50": 590,
    "taste_feedback": ["bitter", "heavy"],
    "psd_stats": GOOD_DIST,
    "brew_method": "pour_over",
    "water_temp_c": 97,
    "extraction_time_s": 320,
    "filter_type": "paper",
    "dose_g": 20,
    "water_g": 320,
})

# Test 5: Bimodal distribution
run_test("Bimodal grind + sour → grinder issue", {
    "current_d50": 600,
    "taste_feedback": ["sour"],
    "psd_stats": BIMODAL_DIST,
    "brew_method": "pour_over",
    "water_temp_c": 94,
    "extraction_time_s": 210,
})

# Test 6: Poor uniformity
run_test("Poor uniformity + bitter → temp/time advice", {
    "current_d50": 610,
    "taste_feedback": ["bitter"],
    "psd_stats": POOR_DIST,
    "brew_method": "pour_over",
    "water_temp_c": 94,
    "extraction_time_s": 250,
})

# Test 7: Mixed signals
run_test("Mixed signals → diagnose evenness", {
    "current_d50": 600,
    "taste_feedback": ["sour_and_bitter"],
    "psd_stats": GOOD_DIST,
    "brew_method": "pour_over",
    "water_temp_c": 94,
    "extraction_time_s": 220,
})

# Test 8: Wrong filter for method
run_test("Metal filter on pour-over → flag unusual filter", {
    "current_d50": 620,
    "taste_feedback": ["muddy", "heavy"],
    "psd_stats": GOOD_DIST,
    "brew_method": "pour_over",
    "water_temp_c": 94,
    "extraction_time_s": 230,
    "filter_type": "metal",
    "dose_g": 20,
    "water_g": 320,
})

# Test 9: Full user flow with taste parser
print(f"\n{'─'*55}")
print("TEST: Full user flow (taste parser → recommendation)")
user_note = "It was too bitter and kind of muddy, heavy body"
tags = parse_taste_notes(user_note, use_llm=False)
result = recommend_filter({
    **BASE,
    "current_d50": 580,
    "taste_feedback": tags,
    "psd_stats": GOOD_DIST,
    "brew_method": "pour_over",
    "water_temp_c": 96,
    "extraction_time_s": 290,
    "filter_type": "paper",
    "dose_g": 20,
    "water_g": 320,
})
print(f"  User note:     \"{user_note}\"")
print(f"  Parsed tags:   {tags}")
print(f"  Mode:          {result['mode']}")
print(f"  Grind:         {result['grind_recommendation']['message'][:100]}")
if result['secondary_advice']['shown']:
    print(f"  Secondary:     {result['secondary_advice']['message'][:100]}")
brew_issues = result.get("brew_analysis", {}).get("issues", [])
for issue in brew_issues:
    print(f"  ⚠️ {issue[:90]}")


print(f"\n{'='*60}")
print("✅ All tests completed!")
print(f"{'='*60}\n")
