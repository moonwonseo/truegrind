"""
recommendation — True Grind recommendation engine package.

Usage:
    from recommendation import recommend_filter, classify_grind_message, parse_taste_notes

    # Step 1: After photo analysis, show initial classification
    message = classify_grind_message(d50=620, brew_method="pour_over")
    # → "Your grind (D50=620µm) is well-suited for Pour-over (V60, Chemex, etc.)."

    # Step 2: Parse user's free-text taste notes
    tags = parse_taste_notes("It was too bitter and muddy")
    # → ["bitter", "muddy"]

    # Step 3: Get full recommendation with all variables
    result = recommend_filter({
        "current_d50": 620,
        "current_setting": 18,
        "fitted_slope": 25,
        "dial_range_min": 1,
        "dial_range_max": 40,
        "taste_feedback": tags,
        "brew_method": "pour_over",
        "water_temp_c": 94,
        "extraction_time_s": 210,
        "filter_type": "paper",
        "dose_g": 20,
        "water_g": 320,
        "psd_stats": psd,
    })
"""

from recommendation.recommendation_engine import (
    recommend_filter,
    classify_grind_message,
    load_rules,
)

from recommendation.taste_parser import parse_taste_notes

__all__ = [
    "recommend_filter",
    "classify_grind_message",
    "parse_taste_notes",
    "load_rules",
]
