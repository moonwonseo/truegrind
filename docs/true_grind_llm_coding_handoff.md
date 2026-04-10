# True Grind Coding Handoff for an LLM

This document is meant to be pasted into an LLM like ChatGPT or Claude so it can help implement the next stage of the **True Grind** project without changing the core architecture.

## What this project is

True Grind is a mobile app that:
1. takes a photo of coffee grounds next to a US quarter,
2. uses computer vision to estimate particle size distribution,
3. extracts metrics like `D50`,
4. compares the measured grind to a target range,
5. tells the user how to adjust their grinder.

The current recommendation layer is **filter coffee only**.

## Important architectural rule

The app should use a **hybrid architecture**:

- **Deterministic recommendation engine** for the actual grind recommendation math
- **Optional LLM layer** for:
  - interpreting messy user tasting notes,
  - personalizing wording,
  - explaining the recommendation clearly,
  - suggesting one secondary variable when allowed

The LLM should **not** decide the actual grind steps or override the math.

## Files included in this bundle

Inside the `recommendation/` folder:

- `rules_filter.json`
  - stores configuration and rule categories for the filter coffee recommendation layer

- `recommendation_engine.py`
  - Python wrapper that reads the JSON rules and returns a structured recommendation object

- `README.md`
  - short usage note

This bundle also includes this markdown file.

## What already exists

The recommendation layer currently supports:
- filter coffee only
- stepped grinders only
- a target D50 for filter coffee
- tolerance checking
- basic taste-note routing
- temperature as the first secondary variable if grind is already close to target

## What the current engine is supposed to do

Input:
- `current_d50`
- `current_setting`
- `fitted_slope`
- `dial_range_min`
- `dial_range_max`
- `taste_feedback`

Optional input:
- `drawdown_time_s`
- `water_temp_c`
- `dose_g`
- `water_g`
- `agitation_level`
- `grinder_model`

Output:
- grind direction
- step count
- new setting
- optional secondary advice
- confidence labels

## Core principle

The recommendation engine should be the source of truth for:
- finer vs coarser
- step count
- dial clamping
- tolerance bands
- confidence labels
- burr drift flags later

The LLM should only:
- convert messy notes into structured taste tags
- explain the result in plain English
- personalize wording based on user preferences
- summarize patterns over time

## How this fits into the project

The flow should be:

`photo -> grind_pipeline.py -> PSD output dict -> recommendation_engine.py -> recommendation object -> UI`

The recommendation engine should be called **after** the vision pipeline has already returned values like `D50`.

## Suggested folder structure

```text
coffee-grind-analyzer/
├── grind_pipeline.py
├── recommendation/
│   ├── rules_filter.json
│   ├── recommendation_engine.py
│   ├── README.md
│   ├── state_store.py              # future
│   ├── drift_monitor.py            # future
│   └── models.py                   # future
├── llm/
│   ├── note_interpreter.py         # future
│   ├── explainer.py                # future
│   ├── prompts.py                  # future
│   └── validators.py               # future
```

## What I need help coding next

I want help integrating the recommendation layer into the existing project.

### Immediate coding goal
Help me plug `recommendation_engine.py` into my existing pipeline so that once the image is processed and `D50` is returned, the app can generate a recommendation.

### Concrete tasks
1. Inspect my project structure and tell me where to import the recommendation engine.
2. Show me exactly how to call:
   `recommend_filter(payload)`
3. Help me pass the PSD output into the recommendation engine.
4. Help me return the recommendation object to the frontend or CLI output.
5. Keep the code simple and beginner-friendly.

## Example of how the engine should be called

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

## What I want from the LLM when helping me code

When you help me, please:
- explain where each file should go,
- explain what each file does,
- show exact code edits instead of only describing them,
- assume I am not technical,
- avoid skipping steps,
- tell me which file to open and what to paste,
- do not redesign the architecture unless necessary.

## How the future LLM layer should work

The future LLM layer should sit **on top** of the deterministic engine.

### LLM note interpreter
Goal:
Turn messy notes like:

> “kind of hollow, bright up front, maybe thin”

into something structured like:

```json
{
  "taste_tags": ["sour", "thin", "hollow"],
  "mixed_defect_flag": false,
  "confidence": "high"
}
```

### LLM explainer
Goal:
Take the already-computed recommendation and produce a friendlier explanation like:

```json
{
  "headline": "Go 2 clicks finer",
  "body": "Your grounds measured a bit coarser than your target filter range, which fits with your note that the cup tasted thin and hollow. I’d move from 18 to 16 first, then brew again before changing anything else.",
  "follow_up": "If it still tastes sharp after that, I’d try slightly hotter water next.",
  "confidence_label": "high"
}
```

## Critical safety rule for the future LLM layer

The LLM must **not**:
- override the grind direction,
- override the step count,
- invent a new target setting,
- ignore confidence or uncertainty.

It may only:
- interpret notes,
- explain the result,
- personalize the presentation,
- suggest at most one approved secondary variable.

## What “learning user preferences” should mean

This should mostly happen through normal app logic and stored user history, not by relying on the LLM to remember things.

Examples of useful stored preferences:
- preferred flavor profile: brighter / sweeter / balanced
- accepted recommendation rate
- preferred secondary variable types
- disliked secondary variable types
- grinder model
- calibration history
- recent brews

## What “burr wear” should mean

Burr wear should be handled by monitoring calibration drift over time.

Examples:
- compare current fitted slope to older fitted slope
- compare user slope to expected grinder-model average
- if drift is large enough, flag recalibration

This should be implemented in normal Python logic, not decided by the LLM.

## What I want built after integration

After the current integration works, help me build these next pieces in order:

### Phase 1
- integrate the deterministic recommendation engine into the existing pipeline
- test with mock payloads
- print the result to terminal or API response

### Phase 2
- add a simple user history store
- save brew results and preferences
- track repeated patterns

### Phase 3
- add an LLM note interpreter
- convert messy tasting notes into structured tags
- validate the LLM output against a schema

### Phase 4
- add an LLM explainer
- use structured engine output plus user preferences to generate a personalized explanation
- keep the grind math unchanged

### Phase 5
- add burr drift detection
- flag recalibration when the user’s grinder appears to have drifted

## Constraints

- Keep this as an MVP-first implementation.
- Do not overengineer.
- Keep the core recommendation deterministic.
- Use beginner-friendly code.
- If there is a choice between clever and clear, choose clear.

## Preferred style of help

When helping me code:
- show exact edits,
- tell me where to put files,
- tell me what command to run,
- tell me what output I should expect,
- explain errors in plain English if something fails.

## Final request to the LLM

Please help me implement this project step by step inside my existing VS Code project, beginning with integration of the deterministic recommendation engine after the vision model returns `D50`.
