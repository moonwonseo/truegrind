# Recommendation layer starter files

This folder contains a simple starter implementation for the **filter coffee recommendation layer**.

## Files
- `rules_filter.json` -> configuration and rule categories
- `recommendation_engine.py` -> Python wrapper that reads the rules and returns a recommendation object

## How this fits into your project
Your project flow becomes:

`photo -> grind_pipeline.py -> PSD output dict -> recommendation_engine.py -> recommendation object -> UI`

The recommendation engine expects values like:
- `current_d50`
- `current_setting`
- `fitted_slope`
- `dial_range_min`
- `dial_range_max`
- `taste_feedback`

## Simplest next step
In the file that currently runs your vision pipeline, do something like this:

```python
from recommendation.recommendation_engine import recommend_filter

psd_output = {
    "D50": 670
}

payload = {
    "current_d50": psd_output["D50"],
    "current_setting": 18,
    "fitted_slope": 25,
    "dial_range_min": 1,
    "dial_range_max": 40,
    "taste_feedback": ["sour", "thin"]
}

result = recommend_filter(payload)
print(result)
```

## Important
This is a **starter layer**:
- it only supports **filter coffee**
- it assumes a **stepped grinder**
- it uses **temperature** as the first secondary variable when grind is already close to target
- it does **not** replace your backend or frontend yet

You still need to call this Python file from wherever your app currently handles the pipeline output.
