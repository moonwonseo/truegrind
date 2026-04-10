"""
Simple filter-coffee recommendation engine for True Grind.

What this file does:
1. Loads JSON rules from rules_filter.json
2. Accepts PSD output / grinder calibration values after the vision model runs
3. Returns a recommendation object the frontend can show to the user

This is intentionally simple and readable. It is a starter layer, not a full backend.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


RULES_PATH = Path(__file__).with_name("rules_filter.json")


def load_rules(path: Path = RULES_PATH) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(value, maximum))


def _normalize_taste_feedback(taste_feedback: Any) -> List[str]:
    """Accepts either a string or a list of strings and normalizes to lowercase list."""
    if taste_feedback is None:
        return []

    if isinstance(taste_feedback, str):
        items = [taste_feedback]
    elif isinstance(taste_feedback, list):
        items = taste_feedback
    else:
        raise TypeError("taste_feedback must be a string or list of strings")

    normalized: List[str] = []
    for item in items:
        if not isinstance(item, str):
            continue
        normalized.append(item.strip().lower())
    return normalized


def _has_any(values: List[str], targets: List[str]) -> bool:
    return any(v in targets for v in values)


def recommend_filter(payload: Dict[str, Any], rules: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """
    Main entry point.

    Expected payload keys:
      - current_d50 (float)
      - current_setting (float)
      - fitted_slope (float)
      - dial_range_min (float)
      - dial_range_max (float)
      - taste_feedback (str | list[str])

    Optional:
      - drawdown_time_s
      - water_temp_c
      - dose_g
      - water_g
      - agitation_level
      - grinder_model
    """
    rules = rules or load_rules()

    required = rules["inputs"]["required"]
    missing = [field for field in required if field not in payload]
    if missing:
        raise ValueError(f"Missing required input(s): {', '.join(missing)}")

    current_d50 = float(payload["current_d50"])
    current_setting = float(payload["current_setting"])
    fitted_slope = float(payload["fitted_slope"])
    dial_range_min = float(payload["dial_range_min"])
    dial_range_max = float(payload["dial_range_max"])
    taste_feedback = _normalize_taste_feedback(payload["taste_feedback"])

    if fitted_slope == 0:
        raise ValueError("fitted_slope cannot be 0")

    constants = rules["constants"]
    groups = rules["taste_groups"]
    messages = rules["messages"]

    target_d50 = float(constants["target_d50_um"])
    absolute_tolerance = float(constants["absolute_tolerance_um"])

    d50_error_um = current_d50 - target_d50
    tolerance_um = max(absolute_tolerance, abs(fitted_slope) * 0.5)
    within_tolerance = abs(d50_error_um) <= tolerance_um

    raw_adjustment_steps = (target_d50 - current_d50) / fitted_slope
    rounded_adjustment_steps = int(round(raw_adjustment_steps))
    unclamped_new_setting = current_setting + rounded_adjustment_steps
    clamped_new_setting = clamp(unclamped_new_setting, dial_range_min, dial_range_max)

    # If clamping changed the value, recompute final displayed steps from actual movement.
    final_steps = int(round(clamped_new_setting - current_setting))

    under = groups["underextracted_signals"]
    over = groups["overextracted_signals"]
    mixed = groups["mixed_signals"]
    balanced = groups["balanced_signals"]

    response: Dict[str, Any] = {
        "mode": "fallback",
        "inputs_used": {
            "current_d50": current_d50,
            "current_setting": current_setting,
            "fitted_slope": fitted_slope,
            "dial_range_min": dial_range_min,
            "dial_range_max": dial_range_max,
            "taste_feedback": taste_feedback,
        },
        "derived": {
            "target_d50_um": target_d50,
            "d50_error_um": round(d50_error_um, 2),
            "tolerance_um": round(tolerance_um, 2),
            "within_tolerance": within_tolerance,
            "raw_adjustment_steps": round(raw_adjustment_steps, 2),
        },
        "grind_recommendation": {
            "direction": "hold",
            "steps": 0,
            "from_setting": current_setting,
            "to_setting": current_setting,
            "message": messages["fallback"],
        },
        "secondary_advice": {
            "shown": False,
            "type": None,
            "direction": None,
            "message": None,
        },
        "confidence": {
            "grind": "low",
            "secondary": "low",
        },
    }

    # 1) Balanced: hold
    if _has_any(taste_feedback, balanced):
        response["mode"] = "hold"
        response["grind_recommendation"] = {
            "direction": "none",
            "steps": 0,
            "from_setting": current_setting,
            "to_setting": current_setting,
            "message": messages["balanced"],
        }
        response["confidence"] = {"grind": "medium", "secondary": "none"}
        return response

    # 2) Mixed defect: diagnose evenness first
    if _has_any(taste_feedback, mixed):
        response["mode"] = "diagnose_evenness_first"
        response["grind_recommendation"] = {
            "direction": "hold",
            "steps": 0,
            "from_setting": current_setting,
            "to_setting": current_setting,
            "message": messages["mixed"],
        }
        response["secondary_advice"] = {
            "shown": True,
            "type": "technique",
            "direction": "stabilize",
            "message": messages["mixed_secondary"],
        }
        response["confidence"] = {"grind": "low", "secondary": "medium"}
        return response

    # 3) If grind is meaningfully off target, prioritize grind first
    if not within_tolerance:
        if final_steps < 0:
            direction = "finer"
        elif final_steps > 0:
            direction = "coarser"
        else:
            direction = "hold"

        if direction == "finer":
            msg = f"Your grounds are coarser than target. Go finer from {current_setting:g} to {clamped_new_setting:g}."
        elif direction == "coarser":
            msg = f"Your grounds are finer than target. Go coarser from {current_setting:g} to {clamped_new_setting:g}."
        else:
            msg = "Your grind appears off target, but the new setting was clamped by the grinder's dial range."

        response["mode"] = "primary_grind"
        response["grind_recommendation"] = {
            "direction": direction,
            "steps": abs(final_steps),
            "from_setting": current_setting,
            "to_setting": clamped_new_setting,
            "message": msg,
        }
        response["confidence"] = {"grind": "high", "secondary": "none"}
        return response

    # 4) If grind is already close, recommend one non-grind variable
    secondary_step = constants["default_secondary_step"]

    if _has_any(taste_feedback, under):
        response["mode"] = "secondary_variable"
        response["grind_recommendation"] = {
            "direction": "hold",
            "steps": 0,
            "from_setting": current_setting,
            "to_setting": current_setting,
            "message": "Your grind is already close to target.",
        }
        response["secondary_advice"] = {
            "shown": True,
            "type": "temperature",
            "direction": "increase",
            "message": f"Try slightly hotter water: about +{secondary_step['temperature_c']}°C.",
        }
        response["confidence"] = {"grind": "medium", "secondary": "medium"}
        return response

    if _has_any(taste_feedback, over):
        response["mode"] = "secondary_variable"
        response["grind_recommendation"] = {
            "direction": "hold",
            "steps": 0,
            "from_setting": current_setting,
            "to_setting": current_setting,
            "message": "Your grind is already close to target.",
        }
        response["secondary_advice"] = {
            "shown": True,
            "type": "temperature",
            "direction": "decrease",
            "message": f"Try slightly cooler water: about -{secondary_step['temperature_c']}°C.",
        }
        response["confidence"] = {"grind": "medium", "secondary": "medium"}
        return response

    # 5) Fallback
    return response


if __name__ == "__main__":
    # Example input you can run directly:
    example_payload = {
        "current_d50": 670,
        "current_setting": 18,
        "fitted_slope": 25,
        "dial_range_min": 1,
        "dial_range_max": 40,
        "taste_feedback": ["sour", "thin"],
        "drawdown_time_s": 170,
        "water_temp_c": 93,
        "dose_g": 20,
        "water_g": 320,
        "agitation_level": "medium",
        "grinder_model": "Baratza Encore",
    }

    result = recommend_filter(example_payload)
    print(json.dumps(result, indent=2))
