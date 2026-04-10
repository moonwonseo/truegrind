# True Grind — Consolidated Product Context

> **How to use this file:** paste it as the first message in a new ChatGPT or Claude chat. It contains everything needed to work on True Grind without re-explaining history. It consolidates work done across multiple Claude and ChatGPT sessions, with newer decisions overriding older ones where they conflict.

---

## 1. Product name

**True Grind**

## 2. One-line description

True Grind is a mobile app that photographs coffee grounds next to a US quarter, estimates particle size distribution in microns using computer vision, and tells the user how to adjust their grinder dial to hit a target grind size for their brew method.

---

## 3. The problem

Home coffee users dial in their grinders by guesswork. Specifically:

1. **Grind size is described vaguely.** "Medium," "medium-fine," "table salt" — none of this is measurable, and most people have no idea what particle size they're actually brewing with.
2. **Grinder dials are not standardized.** Setting "15" on one grinder is nothing like "15" on another. Settings are not portable across brands, and not even stable over time on the same grinder as burrs wear.
3. **Burrs wear and beans vary.** The same dial setting produces different output over months of use, and different roasts shift output at a fixed setting.
4. **Dialing in wastes coffee, time, and patience.** Users typically burn through multiple failed brews to converge, and often don't know whether the problem is grind, temperature, agitation, ratio, or technique.
5. **No accessible at-home measurement tool exists.** Lab-grade particle sizing costs thousands. There is nothing in the middle for enthusiasts.

## 4. Why this product exists

True Grind makes grind size **visible, measurable, and actionable** for home brewers. The core premise: grind size is one of the most important and least visible variables in coffee brewing, and a phone camera plus a known scale reference can deliver enough signal to produce useful adjustment advice.

The product turns a vague sensory problem into a measurable workflow:

**photo → particle measurement → grind diagnosis → grinder adjustment recommendation**

---

## 5. Core user

**Home coffee enthusiast**, especially someone brewing **filter coffee**, who wants more consistency without buying specialized hardware. This user:

- cares about brew quality
- owns a burr grinder
- is willing to take a photo and do light setup
- wants practical, concrete recommendations
- wants to reduce waste and speed up dial-in

**Secondary future users** (not MVP): hobbyists comparing grinders, recipe-sharing communities, content creators, coffee educators.

---

## 6. Current MVP scope — **filter coffee only**

This is a deliberate narrowing from the original multi-brew-method concept. The MVP focuses on **filter coffee**, on **stepped burr grinders**, with **self-calibration**.

**Why filter first:**
- clearest early use case
- reduces scope dramatically
- avoids espresso-level precision demands
- the user only needs resolution from the mid-hundreds of microns and up, not espresso fines
- more realistic for a first working demo

Espresso, moka pot, French press, and coarse categories are **deferred**, not canceled. The earlier five-category classification concept still exists in the codebase but is out of scope for MVP shipping.

---

## 7. The core solution

User places ground coffee on **white paper** next to a **US quarter**, takes an **overhead photo**. The app then:

1. detects the quarter
2. computes scale from pixels to millimeters (`px_per_mm`)
3. segments individual coffee particles
4. estimates per-particle size in microns
5. aggregates into a particle size distribution (PSD)
6. extracts metrics: `D10`, `D50`, `D90`, mean, std, span
7. compares measured grind to the target range for the chosen brew method
8. recommends how many dial steps to adjust the grinder
9. optionally, if grind is already near target, suggests one secondary brewing variable to adjust instead

### Why the US quarter
The quarter has a fixed known diameter (24.26mm), is common, flat, and easier for users than a custom calibration card. It is the **hardcoded** scale reference — no other coins, no AR, no known-distance tricks.

### Capture assumptions
Intentional MVP tradeoff: constrain the user workflow a bit so the measurement layer can work better.

- grounds on **white paper**
- **overhead** photo
- **reasonably consistent** lighting
- quarter in the **same plane** as the grounds
- particles **sufficiently separated** for segmentation

---

## 8. Technical architecture

### Measurement pipeline
1. **Quarter detection** — **Hough Circle Transform** (deterministic, no ML). Produces `px_per_mm`.
2. **Particle segmentation** — **YOLOv8-Seg** (instance segmentation). Single class: `particle`. Chosen over Mask R-CNN for speed, mobile suitability, and accessibility.
3. **Per-particle measurement** — pixel area → equivalent circular diameter in µm.
4. **Distribution analysis** — `D10`, `D50`, `D90`, mean, std, span.
5. **Grind diagnosis** — compare `D50` against target range for the selected brew method.
6. **Recommendation** — deterministic engine (see §9) produces dial adjustment.

### Why `D50` is the primary metric
Median particle diameter in microns. It's the simplest, most understandable bridge between vision output and grinder adjustment, and it's what the first recommendation layer operates on.

### Why `span` matters (future)
`span = (D90 - D10) / D50` measures distribution width / uniformity. Not used in the initial recommendation layer, but important later because an average can look fine while uniformity is bad — and that explains cups that "should" taste right but don't.

### EMPS dataset — evaluated and rejected
The Electron Microscopy Particle Segmentation dataset was considered for pretraining. Verdict: **useful only for pretraining the segmentation task**, not for scale or size info. Reasons: nm-vs-µm domain mismatch, burned-in scale bar artifacts in the source images.

---

## 9. Recommendation logic — **deterministic by design**

This is a **critical architectural decision**: the core grinder recommendation is produced by a **deterministic rules/math engine**, *not* an LLM.

### Why deterministic
- consistency
- explainability
- testability
- debuggability
- trust — users won't believe an LLM that freely invents grinder steps

### Current formula
Assumes a **linear** relationship between dial setting and `D50` within the normal brewing range:

```
adjustment_steps = (target_d50 - current_d50) / fitted_slope
new_setting = round(current_setting + adjustment_steps)
new_setting = clamp(new_setting, dial_min, dial_max)
```

### Why linear
- simple
- realistic enough for MVP
- the app will only have 2–3 calibration points early on
- a more complex curve would overfit without evidence it's justified

This is a deliberate simplification, not a shortcut to revisit lightly.

### Engine inputs
- `current_d50`
- brew method
- current grinder setting
- fitted slope / intercept (from user calibration)
- dial range (min/max)
- tasting notes / feedback (optional)
- optionally: drawdown time, temperature, agitation, ratio

### Engine outputs
- direction (`finer` / `coarser`)
- magnitude (step count)
- target setting
- confidence label
- optional one-variable secondary suggestion

### One-variable-at-a-time rule
If the app recommended grind, temp, agitation, ratio, and contact time all at once, it would be noise. The rule:
- **If `D50` is meaningfully off target** → recommend grinder move only.
- **If `D50` is already near target** → suggest one secondary variable (temperature, agitation, ratio, or contact time).
- **If tasting notes are contradictory** (e.g. both sour and bitter, suggesting uneven extraction) → avoid overconfident grinder advice; flag as possible technique issue.

---

## 10. Calibration philosophy — self-calibration first

The app must be useful for a **solo user with zero network effects**.

### Self-calibration flow
1. User grinds at a known dial setting
2. Measures `D50`
3. Grinds at a second known dial setting
4. Measures `D50` again
5. App fits a simple linear slope between dial and `D50`
6. Fit improves as the user adds more measurements over time

**Minimum 2 calibration points** to produce a slope.

### Why this matters
It directly solves the "same dial number means different things across grinders" problem by personalizing the mapping to the user's specific hardware.

### Future expansion
Crowdsourced priors: once enough users calibrate the same grinder model, new users can start from an average curve and replace it with their own data as they calibrate. Deferred — not needed to prove single-user value.

---

## 11. Role of an LLM in this product

The product has explored using an LLM and concluded: **LLM as sidecar, never as the recommender.**

### LLM is useful for
- interpreting messy tasting notes into structured tags
- generating clearer user-facing explanations
- personalizing tone and coaching
- summarizing patterns over time

### LLM is NOT used for
- grind-step calculation
- dial mapping math
- calibration fitting
- burr-wear detection
- drift monitoring
- primary grind recommendation logic

### Architecture
```
vision model → deterministic recommendation engine → optional LLM explanation layer
```

### LLM sidecar roles (future)

**1. Note interpreter.** Takes messy notes like *"kind of hollow, a little sharp, maybe thin, dusty finish"* and returns:
```json
{
  "taste_tags": ["sour", "thin", "hollow", "dry"],
  "mixed_defect_flag": false,
  "confidence": "medium"
}
```

**2. Personalized explainer.** Takes the measured `D50`, target, calibrated recommendation, user preferences, and parsed tasting tags, and returns:
```json
{
  "headline": "Go 2 clicks finer",
  "body": "Your grounds measured coarser than your filter target, which matches your note that the cup tasted thin. I'd move from 18 to 16 and keep everything else the same.",
  "follow_up": "If it still tastes sharp, try slightly hotter water next.",
  "confidence_label": "high"
}
```

**3. Preference-aware language.** Frames advice around the user's known preferences (sweeter vs brighter, minimal intervention vs experimental, etc.).

### Critical rule
**The LLM must never override the grind-step output from the deterministic engine.**

---

## 12. Preference learning

Preferences are handled through **structured stored data**, not LLM memory. Examples:
- preferred flavor profile (brighter / sweeter / balanced)
- accepted recommendation rate
- most successful secondary variables
- disliked advice types
- average brews to convergence
- favorite brew devices
- common beans / roasts

The LLM can *read* this profile; it is not the system of record.

---

## 13. Burr wear monitoring (future)

Framed as a **calibration drift** problem, not a separate model:
- store calibration points over time
- refit slope and intercept as new points arrive
- compare recent slope to earlier slope or grinder-model average
- if drift exceeds threshold, surface a recalibration warning

Handled deterministically, not via LLM prose inference.

---

## 14. Locked decisions (do not relitigate)

- **US quarter (24.26mm)** as the hardcoded scale reference
- **All sizes in µm internally**, never mm or px in user-facing outputs
- **`D50`** as the primary adjustment metric
- **Linear dial↔`D50`** model for calibration
- **Self-calibration first**, crowdsourcing later
- **Filter coffee only** for MVP
- **Stepped burr grinders only** for MVP
- **No blade grinder support**, ever
- **Stepless grinders** = lower priority, not MVP
- **Deterministic rules/math engine** for the recommendation
- **LLM as sidecar only** — note interpretation and explanation, never the recommender
- **YOLOv8-Seg** for particle segmentation, single class `particle`
- **Hough Circle Transform** for quarter detection (not ML)
- **Minimum 2 calibration points** to produce a slope
- **One secondary variable at a time** when suggesting non-grind adjustments

---

## 15. Non-goals (don't design around these)

- blade grinder support
- first-class stepless grinder support
- espresso-grade precision in MVP
- a universal coffee oracle
- brew recipe generation
- lab-grade accuracy claims
- streaming training data from cloud
- letting the LLM decide grinder settings

---

## 16. What is built

### Files that exist in the repo
- `grind_pipeline.py` — full inference + training pipeline (quarter detection, YOLOv8-Seg inference, px-to-µm conversion, PSD computation, grind classification)
- `emps_to_yolo.py` — EMPS Supervisely bitmap → YOLOv8-Seg format converter (verified against real annotation files)
- `r2_manager.py` — Cloudflare R2 dataset manager (boto3, parallel upload/sync/download)
- `bootstrap.py`
- `pyproject.toml`, `uv.lock`
- `/frontend` — SvelteKit scaffold
- `coffeegrindsize.py` — earlier prototype using pure NumPy + PIL with brightness thresholding and cost-path clustering (no OpenCV). "Classical image processing." Useful as a fallback / baseline.

### Created during planning/build
- starter `recommendation_engine.py`
- `rules_filter.json`
- markdown handoff docs for integrating the recommendation layer
- starter recommendation bundle zip for a new coding chat

### ⚠️ Important caveat — vision model readiness
The vision pipeline is **structurally complete** but **not yet trained/fine-tuned on real coffee photos**. A 500-image synthetic dataset with 17,000+ labeled particles was created for an earlier capstone/presentation prototype, but the production model for the shipping app is still an open training task. **The recommendation layer and other downstream work can and should proceed in parallel with model training** — they don't need to wait.

---

## 17. What is NOT built yet

- production-trained coffee segmentation model
- recommendation engine wired into the live pipeline
- self-calibration UI flow
- persistence / database layer for calibration and history
- React Native mobile app
- backend API wrapper
- crowdsourced grinder database
- burr drift monitoring
- user preference learning
- journaling / recipe memory
- LLM note interpreter
- LLM personalized explainer

---

## 18. Roadmap (6 phases)

1. **Phase 1** — integrate the deterministic recommendation layer after the vision pipeline
2. **Phase 2** — make the filter-only flow usable end-to-end: photo → PSD → recommendation → rebrew loop
3. **Phase 3** — persistence: calibration history, user state, stored brews
4. **Phase 4** — structured preference learning and burr drift monitoring
5. **Phase 5** — LLM sidecar features: note interpreter, personalized explainer
6. **Phase 6** — cautious expansion: more brew methods, more grinder types, community / journaling / analytics if justified

---

## 19. Business intent

### User-value intent
- reduce wasted brews and wasted coffee
- speed up dial-in
- make grind size understandable
- improve brewing consistency
- reduce frustration from vague grinder settings

### Commercial intent
Potential revenue vectors:
- premium enthusiast app
- subscriptions for history, analytics, advanced personalization
- grinder-specific calibration libraries
- recipe journaling and saved brew profiles
- community / sharing features
- partnerships with grinder or hardware brands
- differentiated "AI + computer vision for brewing" positioning

The loop the business is trying to create:
**measurement → recommendation → improvement → retention**

### Long-term defensibility
The per-grinder calibration data. Once enough users calibrate the same grinder model, the app ships with priors and new users skip calibration. That's the network effect — intentionally deferred until single-user value is proven.

---

## 20. Success metrics

### Product
- retention
- repeat use
- time to dial-in
- recommendation acceptance rate
- user-reported helpfulness
- reduction in failed brews before convergence

### Recommendation quality
- movement toward target `D50` after recommendation
- mean absolute `D50` error after adjustment
- calibration quality over time
- consistency across lighting / angle variation
- agreement between measurement and user-reported brew outcome

### UX
- trust in recommendation
- clarity of explanation
- perceived usefulness
- satisfaction with personalization

**Theme:** success is not "the model runs." Success is "the user gets better coffee more reliably."

---

## 21. Open questions

1. Exact target `D50` inside the filter band for MVP (e.g. is it 600µm? 750µm?)
2. Acceptable error tolerance before a recommendation becomes useless
3. Database / persistence choice for calibration and history
4. Source of truth for grinder models and dial ranges (manual list? user-submitted? scraped?)
5. How much bean / roast metadata to capture in MVP
6. How much confidence signaling should be visible in the UI
7. Threshold for burr drift / recalibration warnings
8. When it's worth adding the LLM note interpreter
9. What the simplest end-to-end demo looks like that still proves value
10. Crowdsourced calibration privacy / consent model

---

## 22. Key lessons and insights

### Start narrower than it first sounded
The original concept could easily become "a universal coffee intelligence app." That's too broad. MVP = filter + stepped burr + measurement + adjustment.

### Grind math should be simple before it's fancy
A linear slope, a calibration, and a target `D50` are enough to start producing usable recommendations. No giant prediction engine on day one.

### Solve a real user pain, not showcase AI
**Do not make AI the point.** The user story is "this helps me dial in faster and waste less coffee," not "look at this clever vision model."

### Explainability matters
Recommendations need to visibly connect to the measured `D50`, the target, the user's calibration, and optionally their tasting notes. Black-box advice won't be trusted.

### Image-capture discipline is part of the product
It's not just model training. Workflow design — the white paper, the overhead angle, the quarter placement — is part of product quality.

### Value is in the loop, not the single prediction
The product's value is the workflow: measure → adjust → rebrew → verify → learn. A one-off micron number is not the product.

---

## 23. Product strategy in plain English

1. Start with a real pain: inconsistent grind and guesswork in home coffee
2. Build the simplest measurable solution: photo-based grind measurement with a scale reference
3. Convert measurement into action: deterministic grinder adjustment
4. Keep the MVP narrow: filter coffee, stepped burr grinders, self-calibration first
5. Add trust and clarity: explanations, confidence, confirmation loop
6. Add personalization only after the core loop works: history, preferences, optional LLM note interpretation and explanation
7. Expand only after the measurement-adjustment loop proves value: crowdsourced profiles, more brew methods, better coaching, journaling

---

## 24. Guidance for a new LLM helping on this project

### Assume
- the product is real and conceptually well-formed
- the biggest job now is **turning the architecture into a working product**, not ideation
- the current core is **measurement + deterministic grinder adjustment**
- the current MVP is **filter coffee first**
- any advice should preserve that narrow scope unless there's a strong reason not to
- code suggestions should be beginner-friendly and concrete
- explanations should separate: decided / assumed for MVP / future work / still open

### Help with
- integrating the recommendation engine into the existing pipeline
- improving product docs
- writing clear code integration steps
- suggesting UI logic for the recommendation flow
- designing the user state / preference store
- designing burr drift monitoring
- drafting note-interpreter and explainer prompts
- scoping features using MVP discipline

### Do NOT
- casually redesign the product into something broader
- replace the deterministic recommendation with a freeform LLM
- ignore the self-calibration logic
- overcomplicate the MVP without strong justification
- propose polynomial fits, neural-net recommenders, or multi-variable optimization on day one

---

## 25. Communication preferences (about the person building this)

- Wants concise, direct answers — not formal or rehearsed
- Prefers natural language over jargon
- Will push back on unnecessary complexity
- Has working code already; treat them as the technical owner, not a beginner
- When asked "how does X work," wants the two-sentence version first, not a lecture

---

## Final summary

True Grind is an AI-assisted coffee product that helps home brewers measure grind size from a phone photo and convert that measurement into practical grinder adjustments.

It exists because grind size is hard to see, hard to compare, and hard to standardize across grinders — yet it matters enormously for cup quality.

The product philosophy:
- start narrow (filter coffee, burr grinders)
- measure what matters (`D50`, via quarter-calibrated CV)
- make the recommendation engine deterministic
- use self-calibration
- build trust through explainability
- add LLM intelligence only as a constrained interpretation and personalization layer
- keep the product centered on reducing waste and speeding dial-in

The near-term goal: a working MVP where the user photographs grounds, gets a measured `D50`, receives a grinder recommendation, rebrews, and gradually builds a more personalized calibration profile over time.
