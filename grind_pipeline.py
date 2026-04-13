"""
Coffee Grind Size Pipeline
==========================
1. Detect a US quarter in the image → compute px/mm scale
2. Segment coffee particles using YOLOv8-Seg
3. Convert pixel measurements to microns
4. Compute D10, D50, D90 and full PSD
5. Classify grind category from D50

Dependencies:
    pip install ultralytics opencv-python-headless numpy matplotlib scipy
"""

import cv2
import numpy as np
import matplotlib.pyplot as plt
from scipy import stats
from ultralytics import YOLO
from pathlib import Path
import torch


_cached_device = None

def get_device() -> str:
    """Pick the best available device: CUDA > MPS > CPU. Cached after first call."""
    global _cached_device
    if _cached_device is not None:
        return _cached_device
    if torch.cuda.is_available():
        _cached_device = "cuda"
    elif torch.backends.mps.is_available():
        _cached_device = "mps"
    else:
        _cached_device = "cpu"
    print(f"[Device] Using {_cached_device.upper()}")
    return _cached_device


# ─────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────

QUARTER_DIAMETER_MM = 24.26          # US quarter physical diameter

# D50 thresholds for grind classification (µm)
GRIND_THRESHOLDS = {
    "espresso":    (0,    400),
    "moka_pot":    (400,  500),
    "filter":      (500,  700),
    "french_press":(700,  900),
    "coarse":      (900,  float("inf")),
}


# ─────────────────────────────────────────────────────────────
# STEP 1: QUARTER DETECTION
# ─────────────────────────────────────────────────────────────

def detect_quarter(image_bgr: np.ndarray, debug: bool = False) -> float | None:
    """
    Detect a US quarter in the image using Hough Circle Transform.

    Returns (px_per_mm, circle_info, aspect_ratio) or (None, None, None).
    
    aspect_ratio is minor_axis/major_axis from ellipse fitting:
      - 1.0 = perfect circle (phone perfectly overhead)
      - < 0.92 = tilted camera, measurements will be inaccurate
    """
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (9, 9), 2)

    h, w = gray.shape
    min_r = int(w * 0.04)
    max_r = int(w * 0.18)

    circles = cv2.HoughCircles(
        blurred,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=w // 4,
        param1=60,
        param2=35,
        minRadius=min_r,
        maxRadius=max_r,
    )

    if circles is None:
        print("[WARNING] No quarter detected. Check image or adjust Hough params.")
        return None, None, None

    circles = np.round(circles[0, :]).astype(int)

    best_circle = None
    best_score = -1

    for (cx, cy, r) in circles:
        mask = np.zeros_like(gray)
        cv2.circle(mask, (cx, cy), r, 255, -1)
        mean_val = cv2.mean(gray, mask=mask)[0]

        if 140 < mean_val < 235:
            score = 1.0 - abs(mean_val - 190) / 50
            if score > best_score:
                best_score = score
                best_circle = (cx, cy, r)

    if best_circle is None:
        print("[WARNING] Circles found but none matched quarter brightness profile.")
        return None, None, None

    cx, cy, r = best_circle

    # ── Ellipse fitting for angle detection ──
    # Extract the quarter region and find its contour for ellipse fitting
    quarter_mask = np.zeros_like(gray)
    cv2.circle(quarter_mask, (cx, cy), int(r * 1.1), 255, -1)  # slightly larger than detected
    
    # Threshold the quarter region for a tighter contour
    quarter_region = cv2.bitwise_and(gray, gray, mask=quarter_mask)
    # The quarter is bright (silver) — threshold at brightness midpoint
    _, quarter_thresh = cv2.threshold(quarter_region, 120, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(quarter_thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    aspect_ratio = 1.0  # default: perfect circle
    effective_diameter_px = r * 2  # default: use Hough radius
    
    if contours:
        # Use the largest contour (should be the quarter)
        cnt = max(contours, key=cv2.contourArea)
        if len(cnt) >= 5:  # fitEllipse requires at least 5 points
            ellipse = cv2.fitEllipse(cnt)
            major_axis = max(ellipse[1])
            minor_axis = min(ellipse[1])
            if major_axis > 0:
                aspect_ratio = minor_axis / major_axis
                # Use MAJOR axis for calibration — it's the uncompressed dimension
                # (the true diameter, unaffected by camera tilt)
                effective_diameter_px = major_axis
                print(f"[Quarter] Ellipse: major={major_axis:.1f}px, minor={minor_axis:.1f}px, "
                      f"aspect_ratio={aspect_ratio:.3f}")
    
    px_per_mm = effective_diameter_px / QUARTER_DIAMETER_MM

    print(f"[Quarter] Detected at ({cx}, {cy}), radius={r}px, aspect_ratio={aspect_ratio:.3f}")
    print(f"[Quarter] Scale: {px_per_mm:.2f} px/mm  ({px_per_mm*1000:.1f} px/m)")

    if debug:
        vis = image_bgr.copy()
        cv2.circle(vis, (cx, cy), r, (0, 255, 0), 3)
        cv2.circle(vis, (cx, cy), 3, (0, 0, 255), -1)
        cv2.putText(vis, f"{effective_diameter_px:.0f}px = 24.26mm (AR={aspect_ratio:.2f})",
                    (cx - 80, cy - r - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 0), 2)
        cv2.imshow("Quarter Detection", vis)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    return px_per_mm, (cx, cy, r), aspect_ratio


def crop_around_quarter(
    image_bgr: np.ndarray,
    padding_factor: float = 4.0,
) -> np.ndarray:
    """
    Crop a square region around the detected quarter.

    The crop extends padding_factor × quarter_radius from the quarter center
    in each direction. This ensures YOLO gets a zoomed-in view where
    individual particles are much larger in the 640×640 internal resolution.

    Args:
        image_bgr:      input image
        padding_factor: how many quarter-radii to extend from center (default 4.0)

    Returns:
        Cropped image. If quarter not found, returns original image.
    """
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (9, 9), 2)

    h, w = gray.shape
    min_r = int(w * 0.04)
    max_r = int(w * 0.18)

    circles = cv2.HoughCircles(
        blurred, cv2.HOUGH_GRADIENT, dp=1.2,
        minDist=w // 4, param1=60, param2=35,
        minRadius=min_r, maxRadius=max_r,
    )

    if circles is None:
        return image_bgr

    circles = np.round(circles[0, :]).astype(int)

    # Find the best quarter (same logic as detect_quarter)
    best_circle = None
    best_score = -1
    for (cx, cy, r) in circles:
        mask = np.zeros_like(gray)
        cv2.circle(mask, (cx, cy), r, 255, -1)
        mean_val = cv2.mean(gray, mask=mask)[0]
        if 140 < mean_val < 235:
            score = 1.0 - abs(mean_val - 190) / 50
            if score > best_score:
                best_score = score
                best_circle = (cx, cy, r)

    if best_circle is None:
        return image_bgr

    cx, cy, r = best_circle
    extent = int(r * padding_factor)

    # Compute crop bounds, clamped to image dimensions
    x1 = max(0, cx - extent)
    y1 = max(0, cy - extent)
    x2 = min(w, cx + extent)
    y2 = min(h, cy + extent)

    # Make it square (use the smaller dimension)
    crop_w = x2 - x1
    crop_h = y2 - y1
    side = min(crop_w, crop_h)

    # Re-center the square crop
    center_x = (x1 + x2) // 2
    center_y = (y1 + y2) // 2
    half = side // 2
    x1 = max(0, center_x - half)
    y1 = max(0, center_y - half)
    x2 = min(w, x1 + side)
    y2 = min(h, y1 + side)

    cropped = image_bgr[y1:y2, x1:x2]
    return cropped


# ─────────────────────────────────────────────────────────────
# STEP 2: PARTICLE SEGMENTATION
# ─────────────────────────────────────────────────────────────

# Class names from the fine-tuned model (Roboflow export order)
CLASS_NAMES = {0: "clump", 1: "coffee-grounds-dataset", 2: "silverskin"}
CLASS_GROUND = 1      # the measurable coffee grounds
CLASS_SILVERSKIN = 2   # chaff — excluded from PSD
CLASS_CLUMP = 0        # clumped grounds — flagged

# Clump thresholds
CLUMP_WARN_RATIO = 0.05    # >5% clump area → mild warning
CLUMP_RETAKE_RATIO = 0.15  # >15% clump area → retake photo


def segment_particles(
    image_bgr: np.ndarray,
    model: YOLO,
    conf_threshold: float = 0.25,
    debug: bool = False,
) -> list[dict]:
    """
    Run YOLOv8-Seg on image. Returns list of particle dicts with:
        - mask: binary np.ndarray (H x W)
        - area_px: area in pixels
        - diameter_px: equivalent circular diameter in pixels
        - bbox: (x1, y1, x2, y2)
        - class_id: int (0=clump, 1=coffee-grounds-dataset, 2=silverskin)
        - class_name: str
    """
    results = model.predict(image_bgr, conf=conf_threshold, verbose=False, device=get_device(), imgsz=1920)
    particles = []

    if results[0].masks is None:
        print("[WARNING] No particles detected.")
        return particles

    masks = results[0].masks.data.cpu().numpy()   # (N, H, W)
    boxes = results[0].boxes.xyxy.cpu().numpy()   # (N, 4)
    classes = results[0].boxes.cls.cpu().numpy().astype(int)  # (N,)

    for i, (mask, box, cls_id) in enumerate(zip(masks, boxes, classes)):
        # Resize mask to match original image size
        mask_resized = cv2.resize(
            mask, (image_bgr.shape[1], image_bgr.shape[0]),
            interpolation=cv2.INTER_NEAREST
        ).astype(np.uint8)

        # Erode mask by 2px to remove boundary bloat from YOLO upscaling
        erode_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask_resized = cv2.erode(mask_resized, erode_kernel, iterations=1)

        area_px = int(mask_resized.sum())
        if area_px < 10:
            continue

        # ── Extract individual particles via distance transform local maxima ──
        # Each local maximum in the distance transform corresponds to the center
        # of one particle, with value ≈ that particle's radius.
        dist = cv2.distanceTransform(mask_resized, cv2.DIST_L2, 5)

        # Find local maxima: dilate the distance map, then maxima are where
        # the original equals the dilated version.
        kernel_size = max(3, int(dist.max() * 0.5) | 1)  # odd kernel ~half the max radius
        dilated = cv2.dilate(dist, np.ones((kernel_size, kernel_size)))
        local_max_mask = ((dist == dilated) & (dist > 2)).astype(np.uint8)

        # Label connected components of the local max mask
        n_maxima, labels_max = cv2.connectedComponents(local_max_mask)

        if n_maxima <= 1:
            # No valid maxima — use minor axis as fallback
            contours, _ = cv2.findContours(mask_resized, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                continue
            cnt = max(contours, key=cv2.contourArea)
            if len(cnt) >= 5:
                _, (w_ell, h_ell), _ = cv2.fitEllipse(cnt)
                diameter_px = min(w_ell, h_ell)
            else:
                rect = cv2.minAreaRect(cnt)
                diameter_px = min(rect[1])
            if diameter_px < 2:
                continue
            particles.append({
                "mask": mask_resized,
                "area_px": area_px,
                "diameter_px": diameter_px,
                "bbox": box.astype(int).tolist(),
                "class_id": int(cls_id),
                "class_name": CLASS_NAMES.get(int(cls_id), "unknown"),
            })
        else:
            # Multiple particles detected within this mask
            for label_id in range(1, n_maxima):
                # Get the max distance value for this local maximum
                component_vals = dist[labels_max == label_id]
                if len(component_vals) == 0:
                    continue
                radius_px = component_vals.max()
                if radius_px < 1:
                    continue
                diameter_px = 2.0 * radius_px

                # Use the local max centroid for the bbox
                ys, xs = np.where(labels_max == label_id)
                cx, cy = int(xs.mean()), int(ys.mean())
                r_int = int(radius_px)
                sub_bbox = [cx - r_int, cy - r_int, cx + r_int, cy + r_int]

                particles.append({
                    "mask": mask_resized,  # shared mask (for visualization)
                    "area_px": int(np.pi * radius_px**2),  # estimated individual area
                    "diameter_px": diameter_px,
                    "bbox": sub_bbox,
                    "class_id": int(cls_id),
                    "class_name": CLASS_NAMES.get(int(cls_id), "unknown"),
                })

    # Summarise detections by class
    counts = {}
    for p in particles:
        name = p["class_name"]
        counts[name] = counts.get(name, 0) + 1
    summary = ", ".join(f"{v} {k}" for k, v in counts.items())
    print(f"[Segmentation] {len(particles)} detections: {summary}")

    if debug and particles:
        # Colour code: green=ground, red=silverskin, yellow=clump
        CLASS_COLORS = {CLASS_GROUND: (0, 200, 0), CLASS_SILVERSKIN: (0, 0, 200), CLASS_CLUMP: (0, 200, 200)}
        vis = image_bgr.copy()
        for p in particles:
            color = CLASS_COLORS.get(p["class_id"], (200, 200, 200))
            vis[p["mask"] == 1] = (
                vis[p["mask"] == 1] * 0.5 + np.array(color) * 0.5
            ).astype(np.uint8)
        cv2.imshow("Particle Segmentation (green=ground, red=silverskin, yellow=clump)", vis)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    return particles


def classify_detections(particles: list[dict]) -> dict:
    """
    Separate detections into grounds, silverskin, and clumps.
    Compute clump ratio and generate warnings.

    Returns dict with:
        - grounds: list of particle dicts (class_id == 1)
        - silverskin: list of particle dicts (class_id == 2)
        - clumps: list of particle dicts (class_id == 0)
        - clump_ratio: float (clump area / total ground+clump area)
        - clump_warning: str | None
        - n_silverskin: int
    """
    grounds = [p for p in particles if p["class_id"] == CLASS_GROUND]
    silverskin = [p for p in particles if p["class_id"] == CLASS_SILVERSKIN]
    clumps = [p for p in particles if p["class_id"] == CLASS_CLUMP]

    # Compute clump ratio by area
    total_ground_area = sum(p["area_px"] for p in grounds)
    total_clump_area = sum(p["area_px"] for p in clumps)
    total_area = total_ground_area + total_clump_area
    clump_ratio = total_clump_area / total_area if total_area > 0 else 0.0

    # Generate clump warning
    clump_warning = None
    if clump_ratio > CLUMP_RETAKE_RATIO:
        clump_warning = (
            f"Too many clumps detected ({clump_ratio:.0%} of area). "
            f"Spread the grounds more thinly on the paper and retake the photo."
        )
    elif clump_ratio > CLUMP_WARN_RATIO:
        clump_warning = (
            f"Some clumps detected ({clump_ratio:.0%} of area). "
            f"Results may be less accurate."
        )

    print(f"[Classification] {len(grounds)} grounds, {len(silverskin)} silverskin, {len(clumps)} clumps")
    if clump_warning:
        print(f"[Classification] ⚠️  {clump_warning}")
    if silverskin:
        print(f"[Classification] ℹ️  {len(silverskin)} silverskin pieces excluded from PSD.")

    return {
        "grounds": grounds,
        "silverskin": silverskin,
        "clumps": clumps,
        "clump_ratio": clump_ratio,
        "clump_warning": clump_warning,
        "n_silverskin": len(silverskin),
    }


def split_clusters(
    particles: list[dict],
    px_per_mm: float,
    max_particle_mm: float = 1.2,
) -> list[dict]:
    """
    Post-process detected particles: split large clusters into individual
    grounds using watershed segmentation.

    The YOLOv8 model often detects clumps of coffee grounds as a single
    particle. This function identifies oversized detections (>1.2mm) and
    uses distance-transform + watershed to split them.

    Args:
        particles:           list of particle dicts from segment_particles()
        px_per_mm:           scale from quarter detection
        max_particle_mm:     particles with equiv. diameter above this are
                             candidates for splitting (default 1.2mm = 1200µm)
    Returns:
        Updated particle list with clusters split into sub-particles.
    """
    max_area_px = np.pi * (max_particle_mm * px_per_mm / 2) ** 2
    # Minimum area: skip sub-regions smaller than ~100µm diameter
    min_diameter_mm = 0.1  # 100µm
    min_area_px = np.pi * (min_diameter_mm * px_per_mm / 2) ** 2

    out = []
    n_split = 0

    for p in particles:
        if p["area_px"] <= max_area_px:
            # Small enough to be a single particle — keep as-is
            if p["area_px"] >= min_area_px:
                out.append(p)
            continue

        # This region is too large — try to split it
        mask = p["mask"]

        # Distance transform: peaks = particle centers
        dist = cv2.distanceTransform(mask, cv2.DIST_L2, 5)

        # Use a lower threshold to find more individual cores
        _, sure_fg = cv2.threshold(dist, 0.25 * dist.max(), 255, 0)
        sure_fg = sure_fg.astype(np.uint8)

        # Morphological opening to clean up noise in sure_fg
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        sure_fg = cv2.morphologyEx(sure_fg, cv2.MORPH_OPEN, kernel)

        # Find individual cores via connected components
        n_labels, labels = cv2.connectedComponents(sure_fg)

        if n_labels <= 2:
            # Only one core found — can't split, keep original particle
            out.append(p)
            continue

        # Multiple cores found — use watershed to split
        markers = labels.copy().astype(np.int32)
        markers[mask == 1] = np.where(
            markers[mask == 1] > 0, markers[mask == 1], 0
        )
        markers[mask == 0] = 1

        mask_3ch = cv2.cvtColor(mask * 255, cv2.COLOR_GRAY2BGR)
        cv2.watershed(mask_3ch, markers)

        for label_id in range(2, n_labels + 1):
            sub_mask = (markers == label_id).astype(np.uint8)
            sub_area = int(sub_mask.sum())

            if sub_area < min_area_px:
                continue

            sub_diameter = 2 * np.sqrt(sub_area / np.pi)

            ys, xs = np.where(sub_mask)
            if len(xs) == 0:
                continue
            bbox = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]

            out.append({
                "mask": sub_mask,
                "area_px": sub_area,
                "diameter_px": sub_diameter,
                "bbox": bbox,
                "class_id": p.get("class_id", 1),
                "class_name": p.get("class_name", "coffee-grounds-dataset"),
            })

        n_split += 1

    if n_split > 0:
        print(f"[Cluster Split] Watershed-split {n_split} oversized regions → {len(out)} total particles (was {len(particles)})")
    else:
        print(f"[Cluster Split] No oversized regions found, {len(out)} particles retained.")

    return out


# ─────────────────────────────────────────────────────────────
# STEP 3: CONVERT TO MICRONS
# ─────────────────────────────────────────────────────────────

def pixels_to_microns(diameter_px: float, px_per_mm: float) -> float:
    """Convert a pixel diameter to microns using the quarter-derived scale."""
    diameter_mm = diameter_px / px_per_mm
    return diameter_mm * 1000.0


def compute_diameters_um(particles: list[dict], px_per_mm: float) -> list[float]:
    """Return list of equivalent diameters in microns for all particles."""
    return [pixels_to_microns(p["diameter_px"], px_per_mm) for p in particles]


# ─────────────────────────────────────────────────────────────
# STEP 4: PARTICLE SIZE DISTRIBUTION
# ─────────────────────────────────────────────────────────────

# Distribution category thresholds (µm)
FINES_THRESHOLD_UM = 200       # particles smaller than this are "fines"
BOULDER_THRESHOLD_UM = 1000    # particles larger than this are "boulders"
BIMODAL_FINES_PCT = 15         # if fines% > this AND boulders% > this, flag bimodal
BIMODAL_BOULDER_PCT = 10
HIGH_SPAN_THRESHOLD = 1.5      # span above this = poor uniformity


def compute_psd(diameters_um: list[float]) -> dict:
    """
    Compute standard PSD statistics from a list of particle diameters (µm).

    Returns dict with:
      - D10, D50, D90, mean, std, span
      - fines_pct:   % of particles < 200 µm
      - uniform_pct: % of particles between 200–1000 µm
      - boulders_pct: % of particles > 1000 µm
      - bimodal_flag: True if high fines AND high boulders (grinder issue)
      - uniformity:  'good', 'moderate', or 'poor' based on span
    """
    if not diameters_um:
        return {}

    arr = np.array(diameters_um)
    n = len(arr)

    # Standard PSD metrics
    d10 = float(np.percentile(arr, 10))
    d50 = float(np.percentile(arr, 50))
    d90 = float(np.percentile(arr, 90))
    span = float((d90 - d10) / d50) if d50 > 0 else 0.0

    # Distribution breakdown
    n_fines = int((arr < FINES_THRESHOLD_UM).sum())
    n_boulders = int((arr > BOULDER_THRESHOLD_UM).sum())
    n_uniform = n - n_fines - n_boulders

    fines_pct = round(n_fines / n * 100, 1)
    boulders_pct = round(n_boulders / n * 100, 1)
    uniform_pct = round(n_uniform / n * 100, 1)

    # Bimodal flag: lots of fines AND boulders = grinder alignment issue
    bimodal_flag = (fines_pct > BIMODAL_FINES_PCT and
                    boulders_pct > BIMODAL_BOULDER_PCT)

    # Uniformity rating from span
    if span < 1.0:
        uniformity = "good"
    elif span < HIGH_SPAN_THRESHOLD:
        uniformity = "moderate"
    else:
        uniformity = "poor"

    psd = {
        "n_particles": n,
        "D10": d10,
        "D50": d50,
        "D90": d90,
        "mean_um": float(arr.mean()),
        "std_um": float(arr.std()),
        "min_um": float(arr.min()),
        "max_um": float(arr.max()),
        "span": span,
        # Distribution breakdown
        "fines_pct": fines_pct,
        "uniform_pct": uniform_pct,
        "boulders_pct": boulders_pct,
        "bimodal_flag": bimodal_flag,
        "uniformity": uniformity,
        "raw_diameters_um": arr.tolist(),
    }

    return psd


def plot_psd(psd: dict, save_path: str | None = None):
    """Plot particle size distribution histogram with D10/D50/D90 markers."""
    if not psd:
        print("[WARNING] No PSD data to plot.")
        return

    diameters = np.array(psd["raw_diameters_um"])

    fig, ax = plt.subplots(figsize=(10, 5))

    # Histogram (volume-weighted approximation using d³)
    bins = np.logspace(np.log10(max(diameters.min(), 1)), np.log10(diameters.max()), 40)
    weights = diameters ** 3   # volume proxy
    weights = weights / weights.sum() * 100

    ax.bar(
        bins[:-1], np.histogram(diameters, bins=bins, weights=weights)[0],
        width=np.diff(bins), align="edge",
        color="#6F4E37", alpha=0.75, label="Volume distribution"
    )

    # D10 / D50 / D90 lines
    for label, val, color in [
        ("D10", psd["D10"], "#2196F3"),
        ("D50", psd["D50"], "#FF5722"),
        ("D90", psd["D90"], "#4CAF50"),
    ]:
        ax.axvline(val, color=color, linewidth=2, linestyle="--",
                   label=f"{label} = {val:.0f} µm")

    ax.set_xscale("log")
    ax.set_xlabel("Particle diameter (µm)", fontsize=12)
    ax.set_ylabel("Volume fraction (%)", fontsize=12)
    ax.set_title(
        f"Grind Size Distribution  |  n={psd['n_particles']} particles\n"
        f"D10={psd['D10']:.0f}  D50={psd['D50']:.0f}  D90={psd['D90']:.0f} µm  "
        f"Span={psd['span']:.2f}",
        fontsize=11
    )
    ax.legend()
    ax.grid(True, which="both", alpha=0.3)
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150)
        print(f"[Plot] Saved to {save_path}")
    else:
        plt.show()


# ─────────────────────────────────────────────────────────────
# STEP 5: GRIND CLASSIFICATION
# ─────────────────────────────────────────────────────────────

def classify_grind(d50_um: float) -> str:
    """Map D50 in microns to a grind category."""
    for category, (low, high) in GRIND_THRESHOLDS.items():
        if low <= d50_um < high:
            return category
    return "unknown"


# ─────────────────────────────────────────────────────────────
# MAIN PIPELINE
# ─────────────────────────────────────────────────────────────

def run_pipeline(
    image_path: str,
    model_path: str = "best.pt",   # fine-tuned 3-class model
    conf: float = 0.25,
    debug: bool = False,
    save_plot: str | None = None,
) -> dict:
    """
    Full pipeline: image → PSD + grind classification.

    Uses the 3-class model:
      - coffee-grounds-dataset → measured for PSD
      - silverskin → excluded (chaff, not extractable)
      - clump → flagged with warnings

    Args:
        image_path:  Path to input image (JPG/PNG).
        model_path:  YOLOv8-Seg weights (default: best.pt, the fine-tuned model).
        conf:        Detection confidence threshold.
        debug:       Show intermediate visualizations.
        save_plot:   If set, saves PSD plot to this path.

    Returns:
        dict with psd stats + grind category + class breakdown.
    """
    # Load image
    image = cv2.imread(image_path)
    if image is None:
        raise FileNotFoundError(f"Cannot load image: {image_path}")

    print(f"\n{'='*50}")
    print(f"Processing: {image_path}")
    print(f"Image size: {image.shape[1]}x{image.shape[0]} px")
    print(f"{'='*50}")

    # Step 1: Quarter detection
    px_per_mm, _, _ = detect_quarter(image, debug=debug)
    if px_per_mm is None:
        raise RuntimeError(
            "Quarter not detected. Ensure a US quarter is visible on white paper."
        )

    # Step 2: Particle segmentation (all classes)
    model = YOLO(model_path)
    model.to(get_device())
    all_detections = segment_particles(image, model, conf_threshold=conf, debug=debug)
    if not all_detections:
        raise RuntimeError("No particles detected. Check model or image quality.")

    # Step 2b: Classify into grounds / silverskin / clumps
    detection_info = classify_detections(all_detections)
    grounds = detection_info["grounds"]

    if not grounds:
        raise RuntimeError(
            "No individual coffee grounds detected — only clumps/silverskin found. "
            "Try spreading the grounds more thinly."
        )

    # Step 2c: Split oversized ground detections (watershed)
    grounds = split_clusters(grounds, px_per_mm)

    # Step 3: Convert to microns (grounds only — silverskin excluded)
    diameters_um = compute_diameters_um(grounds, px_per_mm)

    # Step 4: PSD
    psd = compute_psd(diameters_um)

    # Step 5: Classify
    grind_category = classify_grind(psd["D50"])
    psd["grind_category"] = grind_category
    psd["px_per_mm"] = px_per_mm

    # Add class breakdown info
    psd["n_silverskin"] = detection_info["n_silverskin"]
    psd["n_clumps"] = len(detection_info["clumps"])
    psd["clump_ratio"] = detection_info["clump_ratio"]
    psd["clump_warning"] = detection_info["clump_warning"]

    # Report
    print(f"\n{'─'*40}")
    print(f"  Grounds measured   : {psd['n_particles']}")
    print(f"  Silverskin (excl.) : {psd['n_silverskin']}")
    print(f"  Clumps (flagged)   : {psd['n_clumps']}")
    print(f"  Scale              : {px_per_mm:.2f} px/mm")
    print(f"  D10                : {psd['D10']:.1f} µm")
    print(f"  D50 (median)       : {psd['D50']:.1f} µm")
    print(f"  D90                : {psd['D90']:.1f} µm")
    print(f"  Span (D90-D10)/D50 : {psd['span']:.2f}")
    print(f"  Grind category     : {grind_category.upper()}")
    print(f"{'─'*40}")
    print(f"  Distribution:")
    print(f"    Fines   (<{FINES_THRESHOLD_UM}µm)  : {psd['fines_pct']}%")
    print(f"    Uniform            : {psd['uniform_pct']}%")
    print(f"    Boulders (>{BOULDER_THRESHOLD_UM}µm): {psd['boulders_pct']}%")
    print(f"  Uniformity           : {psd['uniformity'].upper()}")
    if psd['bimodal_flag']:
        print(f"  ⚠️  BIMODAL distribution detected — possible grinder issue")
    if psd['clump_warning']:
        print(f"  ⚠️  {psd['clump_warning']}")
    print(f"{'─'*40}\n")

    # Plot
    plot_psd(psd, save_path=save_plot)

    return psd


# ─────────────────────────────────────────────────────────────
# TRAINING HELPER
# ─────────────────────────────────────────────────────────────

def train_particle_model(
    data_yaml: str,
    base_weights: str = "yolov8n-seg.pt",
    epochs: int = 50,
    imgsz: int = 640,
    project: str = "grind_model",
):
    """
    Fine-tune YOLOv8-Seg on your labeled particle dataset.

    Args:
        data_yaml:    Path to your dataset YAML file (Roboflow export format).
        base_weights: Start from pretrained YOLOv8 weights (or EMPS fine-tuned).
        epochs:       Training epochs. 50 is a good start for fine-tuning.
        imgsz:        Input image size. 640 is standard.
        project:      Output directory name.

    Dataset YAML format (data.yaml):
        path: /path/to/dataset
        train: images/train
        val:   images/val
        nc:    1
        names: ['particle']

    Recommended workflow:
        1. Label images in Roboflow (polygon masks around particles)
        2. Export as "YOLOv8 Segmentation" format
        3. Pass the exported data.yaml here
    """
    device = get_device()
    model = YOLO(base_weights)
    model.train(
        data=data_yaml,
        epochs=epochs,
        imgsz=imgsz,
        project=project,
        name="particle_seg",
        device=device,
        batch=16 if device != "cpu" else 8,
        workers=4,
        patience=15,          # early stopping
        augment=True,
        hsv_h=0.01,           # minimal hue shift (grounds are brown)
        hsv_s=0.3,
        hsv_v=0.3,
        fliplr=0.5,
        flipud=0.2,
        degrees=15,           # slight rotation augmentation
        conf=0.25,            # min confidence during val — filters low-scoring noise
        max_det=500,          # cap detections per image to avoid NMS timeout
        nms=True,
    )
    print(f"[Training] Weights saved to {project}/particle_seg/weights/best.pt")


# ─────────────────────────────────────────────────────────────
# ENTRY POINT  (uv run grind  OR  python grind_pipeline.py)
# ─────────────────────────────────────────────────────────────

def cli():
    import argparse

    parser = argparse.ArgumentParser(
        prog="grind",
        description="Coffee Grind Size Pipeline",
    )
    subparsers = parser.add_subparsers(dest="command")

    # Run inference
    infer = subparsers.add_parser("infer", help="Run pipeline on an image")
    infer.add_argument("image", help="Path to input image")
    infer.add_argument("--model", default="best.pt", help="Model weights")
    infer.add_argument("--conf", type=float, default=0.25)
    infer.add_argument("--debug", action="store_true")
    infer.add_argument("--save-plot", default=None, help="Save PSD plot to path")

    # Run training
    train = subparsers.add_parser(
        "train",
        help="Download data if needed, then train (runs end-to-end)"
    )
    train.add_argument(
        "--data-yaml", default="data/data.yaml",
        help="Path to dataset YAML (default: data/data.yaml, auto-built if missing)"
    )
    train.add_argument("--weights", default="yolov8n-seg.pt")
    train.add_argument("--epochs", type=int, default=50)

    args = parser.parse_args()

    if args.command == "infer":
        run_pipeline(
            image_path=args.image,
            model_path=args.model,
            conf=args.conf,
            debug=args.debug,
            save_plot=args.save_plot,
        )

    elif args.command == "train":
        data_yaml = Path(args.data_yaml)
        if not data_yaml.exists():
            print(f"[Train] {data_yaml} not found — downloading datasets first...")
            from roboflow_prep import main as prep_main
            prep_main()
        train_particle_model(
            data_yaml=str(data_yaml),
            base_weights=args.weights,
            epochs=args.epochs,
        )

    else:
        parser.print_help()


if __name__ == "__main__":
    cli()
