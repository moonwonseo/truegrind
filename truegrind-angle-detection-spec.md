# Feature Spec: Quarter Angle Detection & Validation

*Date: April 13, 2026*
*Priority: High — directly affects measurement accuracy, which is the core product promise*

---

## Problem

The quarter-based calibration corrects for zoom and distance but does NOT correct for camera angle. If the phone is tilted even slightly off-vertical, the quarter appears as an ellipse instead of a circle. This causes `px/mm` to be calculated incorrectly, which cascades into a wrong D50.

In testing, two separate photos of the same grounds produced D50 readings of 676µm vs 865µm (28% difference) — too large to be explained by grounds movement alone. The root cause is likely angle variation between shots.

---

## How the Quarter is Currently Detected

In `grind_pipeline.py`, the quarter is detected using **Hough Circle Transform** (`cv2.HoughCircles`). This fits a perfect circle to the quarter. If the phone is tilted, the quarter is actually an ellipse — HoughCircles will still fit a circle to it but will get the diameter wrong, producing an incorrect `px/mm` value.

---

## Proposed Fix: Ellipse Fitting + Aspect Ratio Check

Instead of (or in addition to) Hough Circle Transform, fit an ellipse to the detected quarter contour and check how circular it is.

### Step 1 — Fit an ellipse to the quarter contour
After detecting the quarter region, use `cv2.fitEllipse()` on its contour to get the major and minor axes.

### Step 2 — Compute aspect ratio
```python
major_axis = max(ellipse[1])  # longer diameter
minor_axis = min(ellipse[1])  # shorter diameter
aspect_ratio = minor_axis / major_axis  # 1.0 = perfect circle, lower = more tilted
```

### Step 3 — Threshold and warn
```python
ANGLE_THRESHOLD = 0.92  # empirically tuned — rejects >~23° tilt

if aspect_ratio < ANGLE_THRESHOLD:
    # Add to quality_warnings
    warnings.append({
        "code": "camera_angle",
        "severity": "error",
        "message": f"Camera angle too steep — quarter appears elliptical ({aspect_ratio:.2f})",
        "tip": "Hold your phone directly overhead (bird's-eye view). The quarter should look like a perfect circle, not an oval."
    })
```

### Step 4 — Use corrected diameter
If aspect ratio is acceptable, use the **minor axis** as the true diameter (it's less affected by tilt than the major axis) for the `px/mm` calculation:
```python
true_diameter_px = minor_axis  # more stable than using major axis
px_per_mm = true_diameter_px / QUARTER_DIAMETER_MM  # QUARTER_DIAMETER_MM = 24.26
```

---

## Where to Implement

All changes go in `grind_pipeline.py` in the `detect_quarter()` function, and the warning gets surfaced through `api_server.py`'s existing `quality_warnings` array — no frontend changes needed, the warning system already handles display.

---

## Expected Outcome

- Same grounds photographed at different slight angles should produce D50 values within ~5-8% of each other (vs 28% currently)
- Users get immediate actionable feedback if their angle is off, before analysis runs
- The `px/mm` value becomes more reliable across shots

---

## Calibration Note

The `ANGLE_THRESHOLD = 0.92` value needs empirical tuning. Suggested approach:
1. Take 10 photos at known angles (0°, 5°, 10°, 15°, 20°, 25° tilt)
2. Measure aspect ratio at each angle
3. Find the tilt angle at which D50 error exceeds ~10%
4. Set threshold just below that aspect ratio

---

## Related Issues

- **HEIC vs PNG giving different readings** — iPhone defaults to HEIC format which gets converted on upload at varying quality. Fix: add server-side HEIC→JPEG conversion in `api_server.py` before the image hits the pipeline, or tell users to set iPhone → Settings → Camera → Formats → Most Compatible (JPEG).
- **Shot-to-shot variance from grounds movement** — unavoidable with physical samples. Acceptable ~5-10% variance. Document as expected behavior.

---

## Production Roadmap: Angle Correction Approaches

### Tier 1 — MVP (implement now)
**Ellipse rejection + retake prompt**
- Difficulty: Easy — 20-30 lines of Python in `grind_pipeline.py`
- Catches the worst cases, prompts user to retake
- Doesn't correct — just rejects bad shots
- Limitation: still passes mildly tilted shots with residual error

---

### Tier 2 — V2 (first production release)
**IMU tilt warning in the camera viewfinder**
- Difficulty: Medium — requires React Native (your planned mobile app, not SvelteKit web)
- Read the phone's accelerometer/gyroscope in real time using `react-native-sensors` or the built-in `DeviceMotion` API
- Show a live level indicator in the camera viewfinder — turns green when phone is within 5° of perpendicular
- Only enable the shutter button when tilt is acceptable
- **Why this is better than correcting after the fact:** prevents the problem entirely, no CV complexity, works in all lighting conditions
- **Why it's not available yet:** requires React Native, which is planned but not yet built. The SvelteKit web app can access `DeviceOrientationEvent` in the browser but it's less reliable and requires user permission on iOS

---

### Tier 3 — V2/V3 (parallel or follow-on)
**Homography correction**
- Difficulty: Medium-Hard — 50-100 lines of OpenCV in `grind_pipeline.py`, but paper corner detection is its own reliability problem
- Detect the four corners of the white paper, compute perspective transform, warp image flat before measuring
- Mathematically corrects for distortion even after the fact
- **Failure modes:** paper corners occluded by grounds, shadows, non-white surfaces, paper not fully in frame
- Best used as a complement to IMU guidance, not a replacement — catches cases where the user ignored the tilt warning

---

### Tier 4 — V3 (full production polish)
**AR-guided capture**
- Difficulty: Hard — requires ARKit (iOS native) or ARCore (Android native), significant platform-specific development
- Uses the phone's AR framework to detect the surface plane and enforce perpendicular alignment in real time
- Only allows capture when phone is within tolerance of true perpendicular to the surface
- This is what professional measurement apps use
- **Why deferred:** requires native iOS/Android development (Swift/Kotlin or advanced React Native AR libraries), significantly more complex than IMU approach, and IMU guidance already solves 90% of the problem at a fraction of the cost

---

## Physical Accessory: TrueGrind Mat

### What it is
A branded mat (paper, silicone, or card stock) that serves as both a physical user guide and a geometric reference for homography correction. The mat replaces the generic "white paper" instruction with a purpose-built calibration surface.

### Why it matters
Homography correction requires reliable detection of four reference points. Plain white paper edges are hard to detect reliably in home lighting conditions — shadows, paper curl, grounds spilling over edges all cause failures. A mat with printed registration markers solves this by giving the algorithm unambiguous anchor points regardless of lighting.

### Mat design elements
- **Corner registration markers** — high-contrast geometric marks (like QR-code corner squares) at each corner that OpenCV can detect instantly and reliably
- **Grounds zone** — clearly marked central area showing where to spread grounds
- **Quarter zone** — dedicated spot (lower-right) showing exactly where to place the quarter, matching the camera viewfinder overlay
- **TrueGrind branding** — logo and product name
- **Size** — standard letter (8.5×11") or A5 — large enough to spread grounds thinly, small enough to fit on a counter

### How the software uses it
1. Detect the four corner registration markers using `cv2.findChessboardCorners()` or contour detection
2. Compute perspective transform using known mat dimensions (fixed physical size = known real-world coordinates)
3. Warp image to flat top-down view
4. Run quarter detection and particle segmentation on corrected image

Using known mat dimensions (vs unknown paper size) makes the homography more accurate because the algorithm knows the exact real-world size of the reference rectangle.

### Business case
- **Free tier:** app works with plain white paper, with ellipse rejection as the safety net
- **Premium / physical product:** TrueGrind mat sold separately ($8-15) — improves accuracy, reduces retakes, looks professional
- **Bundled:** mat + app subscription as a starter kit
- The mat creates a physical touchpoint for the brand and a reason for repeat purchase (consumable paper version vs durable silicone version)
- Grinder brand partnerships — co-branded mats shipped with Fellow Ode, Baratza, etc.

### Implementation priority
Deferred until homography correction is implemented in the pipeline. The mat design can be finalized independently and printed for demo/testing purposes before the software support is built.

---

## Future Enhancement: Homography Correction

The ellipse rejection approach catches obvious tilt cases but doesn't mathematically correct for perspective distortion. Even a shot that passes the aspect ratio check at ~10° tilt will have some residual error because:

- Particles near the edges of a tilted frame are more distorted than particles near the center
- The quarter and the grounds aren't perfectly coplanar if grounds are piled up
- Perspective distortion compresses the apparent size of particles unevenly across the frame

**The proper solution is homography correction:**

1. Detect the four corners of the white paper sheet in the image
2. Compute a perspective transform matrix using `cv2.getPerspectiveTransform()`
3. Warp the entire image to a perfectly flat top-down view using `cv2.warpPerspective()`
4. Run the existing quarter detection and particle segmentation on the corrected image

This fully removes perspective distortion regardless of camera angle, making the quarter calibration accurate even for moderately tilted shots. The white paper provides a natural reference rectangle for corner detection.

**Why this is deferred:**
- Requires reliable paper corner detection, which is its own CV problem (lighting, shadows, paper edges partially covered by grounds)
- Adds latency to the pipeline
- The ellipse rejection approach handles the MVP case adequately by prompting retakes
- Recommended for Phase 3+ once the core measurement loop is validated

---

## Deployment Note

After implementing in `grind_pipeline.py`, redeploy with:
```bash
cd "/Users/moonwonseo/Documents/Coffee Grind Analyzer App"
git add grind_pipeline.py
git commit -m "add quarter angle detection and validation"
git push
python3 -m modal deploy modal_app.py
```

Vercel frontend redeploys automatically on push (no action needed for frontend since warning display is already implemented).
