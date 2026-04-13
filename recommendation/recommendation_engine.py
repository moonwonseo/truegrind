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


def format_setting(value: float) -> str:
    """Format a dial setting as a fraction string: 2.333→'2⅓', 2.667→'2⅔', 3.0→'3'."""
    whole = int(value)
    frac = round((value - whole) * 3) / 3
    if abs(frac - 1/3) < 0.05:
        return f"{whole}⅓"
    elif abs(frac - 2/3) < 0.05:
        return f"{whole}⅔"
    else:
        if abs(frac - 1.0) < 0.05:
            return str(whole + 1)
        return str(whole)


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


def _analyze_brew_variables(
    method_config: Dict[str, Any],
    water_temp_c: float | None,
    extraction_time_s: float | None,
    brew_ratio: float | None,
    filter_type: str | None,
) -> Dict[str, Any]:
    """
    Check brew variables against the ideal ranges for the brew method.
    Returns a dict with flags and messages for any out-of-range variables.
    """
    issues: List[str] = []
    analysis: Dict[str, Any] = {"issues": issues, "all_in_range": True}

    if not method_config:
        return analysis

    # Temperature check
    if water_temp_c is not None:
        ideal_temp = method_config.get("ideal_temp_c", [])
        if len(ideal_temp) == 2:
            analysis["temp_range"] = ideal_temp
            if water_temp_c < ideal_temp[0]:
                issues.append(f"Water temperature ({water_temp_c:.1f}°C) is below ideal range ({ideal_temp[0]}–{ideal_temp[1]}°C). Consider raising it.")
                analysis["temp_status"] = "low"
            elif water_temp_c > ideal_temp[1]:
                issues.append(f"Water temperature ({water_temp_c:.1f}°C) is above ideal range ({ideal_temp[0]}–{ideal_temp[1]}°C). Consider lowering it.")
                analysis["temp_status"] = "high"
            else:
                analysis["temp_status"] = "ok"

    # Extraction time check
    if extraction_time_s is not None:
        ideal_time = method_config.get("ideal_extraction_time_s", [])
        if len(ideal_time) == 2:
            analysis["time_range"] = ideal_time
            if extraction_time_s < ideal_time[0]:
                issues.append(f"Extraction time ({extraction_time_s}s) is shorter than ideal ({ideal_time[0]}–{ideal_time[1]}s). This may cause under-extraction.")
                analysis["time_status"] = "short"
            elif extraction_time_s > ideal_time[1]:
                issues.append(f"Extraction time ({extraction_time_s}s) is longer than ideal ({ideal_time[0]}–{ideal_time[1]}s). This may cause over-extraction.")
                analysis["time_status"] = "long"
            else:
                analysis["time_status"] = "ok"

    # Brew ratio check
    if brew_ratio is not None:
        ideal_ratio = method_config.get("ideal_ratio", [])
        if len(ideal_ratio) == 2:
            analysis["ratio_range"] = ideal_ratio
            analysis["brew_ratio"] = brew_ratio
            if brew_ratio < ideal_ratio[0]:
                issues.append(f"Brew ratio (1:{brew_ratio}) is low — coffee may taste strong/heavy. Try 1:{ideal_ratio[0]}–{ideal_ratio[1]}.")
                analysis["ratio_status"] = "strong"
            elif brew_ratio > ideal_ratio[1]:
                issues.append(f"Brew ratio (1:{brew_ratio}) is high — coffee may taste weak/thin. Try 1:{ideal_ratio[0]}–{ideal_ratio[1]}.")
                analysis["ratio_status"] = "weak"
            else:
                analysis["ratio_status"] = "ok"

    # Filter type check
    if filter_type is not None:
        ideal_filters = method_config.get("filter_types", [])
        if ideal_filters and filter_type.lower() not in ideal_filters:
            issues.append(f"Filter type '{filter_type}' is unusual for this brew method (expected: {', '.join(ideal_filters)}).")
            analysis["filter_status"] = "unusual"
        else:
            analysis["filter_status"] = "ok"

    analysis["all_in_range"] = len(issues) == 0
    return analysis


def classify_grind_message(d50: float, brew_method: str = "pour_over", rules: Dict[str, Any] | None = None) -> str:
    """
    Generate an initial classification message based on D50 and brew method.
    This is shown BEFORE the user provides taste feedback.

    Example: "Your grind (D50=620µm) is well-suited for pour-over brewing."
    """
    rules = rules or load_rules()
    brew_methods = rules.get("brew_methods", {})
    method_config = brew_methods.get(brew_method, {})
    target = method_config.get("target_d50_um", 600)
    description = method_config.get("description", brew_method.replace("_", " "))
    tolerance = 60  # generous tolerance for initial message

    diff = d50 - target

    if abs(diff) <= tolerance:
        return f"Your grind (D50={d50:.0f}µm) is well-suited for {description}."
    elif diff > 0:
        return f"Your grind (D50={d50:.0f}µm) is coarser than ideal for {description} (target ~{target}µm). You may want to grind finer."
    else:
        return f"Your grind (D50={d50:.0f}µm) is finer than ideal for {description} (target ~{target}µm). You may want to grind coarser."


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
      - psd_stats (dict): distribution stats from grind_pipeline.compute_psd().
        Expected keys: fines_pct, boulders_pct, uniform_pct, bimodal_flag,
                       uniformity ('good'/'moderate'/'poor'), span.
      - brew_method (str): 'pour_over', 'french_press', 'aeropress', 'drip', 'moka_pot'
      - water_temp_c (float): water temperature in celsius
      - filter_type (str): 'paper' or 'metal'
      - extraction_time_s (float): total brew/extraction time in seconds
      - num_pours (int): number of pours (pour-over)
      - dose_g (float): coffee dose in grams
      - water_g (float): water weight in grams
      - agitation_level (str): 'low', 'medium', 'high'
      - grinder_model (str)
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
    brew_methods = rules.get("brew_methods", {})

    # Look up brew method to get method-specific targets
    brew_method = payload.get("brew_method", "pour_over")
    method_config = brew_methods.get(brew_method, {})
    target_d50 = float(method_config.get("target_d50_um", constants["target_d50_um"]))
    absolute_tolerance = float(constants["absolute_tolerance_um"])

    # Extract optional brew variables
    water_temp_c = payload.get("water_temp_c")
    extraction_time_s = payload.get("extraction_time_s")
    filter_type = payload.get("filter_type")
    dose_g = payload.get("dose_g")
    water_g = payload.get("water_g")
    num_pours = payload.get("num_pours")
    agitation_level = payload.get("agitation_level")

    # Compute brew ratio if dose and water provided
    brew_ratio = round(water_g / dose_g, 1) if (dose_g and water_g and dose_g > 0) else None

    d50_error_um = current_d50 - target_d50
    tolerance_um = max(absolute_tolerance, abs(fitted_slope) * 0.5)
    within_tolerance = abs(d50_error_um) <= tolerance_um

    # Calculate adjustment in notch increments (1/3 of a full step)
    NOTCH_SIZE = 1 / 3  # each notch is 1/3 of a setting unit
    raw_adjustment_settings = (target_d50 - current_d50) / fitted_slope
    # Round to nearest notch (1/3 step)
    raw_notches = raw_adjustment_settings / NOTCH_SIZE
    rounded_notches = int(round(raw_notches))
    adjustment_in_settings = rounded_notches * NOTCH_SIZE
    unclamped_new_setting = current_setting + adjustment_in_settings
    clamped_new_setting = round(clamp(unclamped_new_setting, dial_range_min, dial_range_max) * 3) / 3

    # Steps = number of notch clicks
    final_notches = int(round((clamped_new_setting - current_setting) / NOTCH_SIZE))

    under = groups["underextracted_signals"]
    over = groups["overextracted_signals"]
    mixed = groups["mixed_signals"]
    balanced = groups["balanced_signals"]

    # Extract optional PSD distribution stats
    psd_stats = payload.get("psd_stats", {})
    bimodal_flag = psd_stats.get("bimodal_flag", False)
    uniformity = psd_stats.get("uniformity", "unknown")
    fines_pct = psd_stats.get("fines_pct", 0)
    boulders_pct = psd_stats.get("boulders_pct", 0)
    uniform_pct = psd_stats.get("uniform_pct", 100)
    span = psd_stats.get("span", 0)

    response: Dict[str, Any] = {
        "mode": "fallback",
        "brew_method": brew_method,
        "inputs_used": {
            "current_d50": current_d50,
            "current_setting": current_setting,
            "fitted_slope": fitted_slope,
            "dial_range_min": dial_range_min,
            "dial_range_max": dial_range_max,
            "taste_feedback": taste_feedback,
            "brew_method": brew_method,
            "water_temp_c": water_temp_c,
            "extraction_time_s": extraction_time_s,
            "filter_type": filter_type,
            "dose_g": dose_g,
            "water_g": water_g,
            "brew_ratio": brew_ratio,
        },
        "derived": {
            "target_d50_um": target_d50,
            "d50_error_um": round(d50_error_um, 2),
            "tolerance_um": round(tolerance_um, 2),
            "within_tolerance": within_tolerance,
            "raw_adjustment_notches": rounded_notches,
        },
        "grind_recommendation": {
            "direction": "hold",
            "steps": 0,
            "from_setting": format_setting(current_setting),
            "to_setting": format_setting(current_setting),
            "message": messages["fallback"],
        },
        "secondary_advice": {
            "shown": False,
            "type": None,
            "direction": None,
            "message": None,
        },
        "brew_analysis": _analyze_brew_variables(
            method_config, water_temp_c, extraction_time_s,
            brew_ratio, filter_type
        ),
        "confidence": {
            "grind": "low",
            "secondary": "low",
        },
        "distribution": {
            "fines_pct": fines_pct,
            "uniform_pct": uniform_pct,
            "boulders_pct": boulders_pct,
            "bimodal_flag": bimodal_flag,
            "uniformity": uniformity,
        },
    }

    # 1) Balanced: hold
    if _has_any(taste_feedback, balanced):
        response["mode"] = "hold"
        response["grind_recommendation"] = {
            "direction": "none",
            "steps": 0,
            "from_setting": format_setting(current_setting),
            "to_setting": format_setting(current_setting),
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
            "from_setting": format_setting(current_setting),
            "to_setting": format_setting(current_setting),
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

    # 2.5) Distribution uniformity check — bimodal or very poor uniformity
    #      means changing grind size won't help; the grinder itself is the issue.
    if bimodal_flag:
        response["mode"] = "grinder_issue"
        response["grind_recommendation"] = {
            "direction": "hold",
            "steps": 0,
            "from_setting": format_setting(current_setting),
            "to_setting": format_setting(current_setting),
            "message": (
                f"Your grind has a bimodal distribution: {fines_pct}% fines "
                f"and {boulders_pct}% boulders. Changing the grind setting "
                f"won't fix this — check your burr alignment or consider "
                f"recalibrating your grinder."
            ),
        }
        response["secondary_advice"] = {
            "shown": True,
            "type": "grinder_maintenance",
            "direction": "check",
            "message": (
                "A bimodal distribution (lots of very fine AND very coarse particles) "
                "usually means the burrs are misaligned, worn, or need cleaning. "
                "Try cleaning and re-seating the burrs before adjusting your grind setting."
            ),
        }
        response["confidence"] = {"grind": "low", "secondary": "high"}
        return response

    if uniformity == "poor" and not bimodal_flag:
        response["mode"] = "poor_uniformity"
        response["grind_recommendation"] = {
            "direction": "hold" if within_tolerance else ("finer" if final_notches < 0 else "coarser"),
            "steps": 0 if within_tolerance else abs(final_notches),
            "from_setting": format_setting(current_setting),
            "to_setting": format_setting(current_setting) if within_tolerance else format_setting(clamped_new_setting),
            "message": (
                f"Your grind has wide distribution (span={span:.2f}, uniformity=poor). "
                f"Only {uniform_pct}% of particles are in the target range. "
                f"Adjusting temperature or contact time may help more than changing grind size."
            ),
        }
        secondary_step = constants["default_secondary_step"]
        if _has_any(taste_feedback, under):
            response["secondary_advice"] = {
                "shown": True,
                "type": "temperature",
                "direction": "increase",
                "message": f"With poor uniformity and sour notes, try hotter water (+{secondary_step['temperature_c']}°C) or longer contact time (+{secondary_step['contact_time_s']}s).",
            }
        elif _has_any(taste_feedback, over):
            response["secondary_advice"] = {
                "shown": True,
                "type": "temperature",
                "direction": "decrease",
                "message": f"With poor uniformity and bitter notes, try cooler water (-{secondary_step['temperature_c']}°C) or shorter contact time (-{secondary_step['contact_time_s']}s).",
            }
        else:
            response["secondary_advice"] = {
                "shown": True,
                "type": "technique",
                "direction": "stabilize",
                "message": "With poor uniformity, focus on consistent technique before changing grind size.",
            }
        response["confidence"] = {"grind": "low", "secondary": "medium"}
        return response

    # 3) If grind is meaningfully off target, prioritize grind first
    if not within_tolerance:
        if final_notches < 0:
            direction = "finer"
        elif final_notches > 0:
            direction = "coarser"
        else:
            direction = "hold"

        from_str = format_setting(current_setting)
        to_str = format_setting(clamped_new_setting)
        notch_word = "notch" if abs(final_notches) == 1 else "notches"
        if direction == "finer":
            msg = f"Your grounds are coarser than target. Go finer {abs(final_notches)} {notch_word}: {from_str} → {to_str}."
        elif direction == "coarser":
            msg = f"Your grounds are finer than target. Go coarser {abs(final_notches)} {notch_word}: {from_str} → {to_str}."
        else:
            msg = "Your grind appears off target, but the new setting was clamped by the grinder's dial range."

        response["mode"] = "primary_grind"
        response["grind_recommendation"] = {
            "direction": direction,
            "steps": abs(final_notches),
            "from_setting": from_str,
            "to_setting": to_str,
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
            "from_setting": format_setting(current_setting),
            "to_setting": format_setting(current_setting),
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
            "from_setting": format_setting(current_setting),
            "to_setting": format_setting(current_setting),
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
        "psd_stats": {
            "fines_pct": 5.2,
            "uniform_pct": 82.1,
            "boulders_pct": 2.3,
            "bimodal_flag": False,
            "uniformity": "good",
            "span": 0.85,
        },
        "drawdown_time_s": 170,
        "water_temp_c": 93,
        "dose_g": 20,
        "water_g": 320,
        "agitation_level": "medium",
        "grinder_model": "Fellow Ode",
    }

    result = recommend_filter(example_payload)
    print(json.dumps(result, indent=2))
