"""
test_recommendation.py — Quick smoke test for the recommendation engine.

Run:  python3 test_recommendation.py  (or:  .venv/bin/python test_recommendation.py)

Tests all the main logic paths:
  1. Grind too coarse → recommends finer
  2. Grind too fine → recommends coarser
  3. Grind near target + sour feedback → secondary advice (raise temp)
  4. Grind near target + bitter feedback → secondary advice (lower temp)
  5. Balanced feedback → hold
  6. Mixed feedback → diagnose evenness
"""

import json
from recommendation.recommendation_engine import recommend_filter

# Base payload — shared values reused in each test
BASE = {
    "current_setting": 18,
    "fitted_slope": 25,
    "dial_range_min": 1,
    "dial_range_max": 40,
}


def run_test(name: str, overrides: dict):
    payload = {**BASE, **overrides}
    result = recommend_filter(payload)
    grind = result["grind_recommendation"]
    secondary = result["secondary_advice"]

    print(f"\n{'─'*50}")
    print(f"TEST: {name}")
    print(f"  D50 input:     {payload['current_d50']} µm")
    print(f"  Taste:         {payload['taste_feedback']}")
    print(f"  Mode:          {result['mode']}")
    print(f"  Grind:         {grind['direction']} {grind['steps']} steps → setting {grind['to_setting']}")
    print(f"  Message:       {grind['message']}")
    if secondary["shown"]:
        print(f"  Secondary:     {secondary['type']} → {secondary['direction']}")
        print(f"  Sec. message:  {secondary['message']}")
    print(f"  Confidence:    grind={result['confidence']['grind']}, secondary={result['confidence']['secondary']}")


# ── Test cases ──────────────────────────────────────────

run_test("Too coarse → go finer", {
    "current_d50": 700,
    "taste_feedback": ["sour", "thin"],
})

run_test("Too fine → go coarser", {
    "current_d50": 500,
    "taste_feedback": ["bitter", "harsh"],
})

run_test("Near target + sour → raise temp", {
    "current_d50": 610,
    "taste_feedback": ["sour"],
})

run_test("Near target + bitter → lower temp", {
    "current_d50": 590,
    "taste_feedback": ["bitter"],
})

run_test("Balanced → hold", {
    "current_d50": 600,
    "taste_feedback": ["balanced"],
})

run_test("Mixed signals → diagnose evenness", {
    "current_d50": 600,
    "taste_feedback": ["sour_and_bitter"],
})

print(f"\n{'='*50}")
print("✅ All 6 tests completed successfully!")
print(f"{'='*50}\n")
