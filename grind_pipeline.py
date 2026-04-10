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


def get_device() -> str:
    """Pick the best available device: CUDA > MPS > CPU."""
    if torch.cuda.is_available():
        device = "cuda"
    elif torch.backends.mps.is_available():
        device = "mps"
    else:
        device = "cpu"
    print(f"[Device] Using {device.upper()}")
    return device


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

    Returns px_per_mm (float) or None if no quarter detected.

    The quarter should be:
      - On a white/light background
      - Unobstructed (not under coffee grounds)
      - In any corner of the frame
    """
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (9, 9), 2)

    # Estimate expected quarter radius range in pixels.
    # A quarter is ~24mm. Assume image captures roughly 150-300mm of width.
    h, w = gray.shape
    min_r = int(w * 0.04)   # quarter ~8% of frame width minimum
    max_r = int(w * 0.18)   # quarter ~18% of frame width maximum

    circles = cv2.HoughCircles(
        blurred,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=w // 4,       # only one quarter expected
        param1=60,
        param2=35,
        minRadius=min_r,
        maxRadius=max_r,
    )

    if circles is None:
        print("[WARNING] No quarter detected. Check image or adjust Hough params.")
        return None

    circles = np.round(circles[0, :]).astype(int)

    # Pick the most silver-colored circle (highest mean gray value ~180-220)
    best_circle = None
    best_score = -1

    for (cx, cy, r) in circles:
        # Sample pixels inside circle
        mask = np.zeros_like(gray)
        cv2.circle(mask, (cx, cy), r, 255, -1)
        mean_val = cv2.mean(gray, mask=mask)[0]

        # Quarter is silver: expect mean brightness 150-230
        if 140 < mean_val < 235:
            score = 1.0 - abs(mean_val - 190) / 50   # prefer ~190 gray
            if score > best_score:
                best_score = score
                best_circle = (cx, cy, r)

    if best_circle is None:
        print("[WARNING] Circles found but none matched quarter brightness profile.")
        return None

    cx, cy, r = best_circle
    diameter_px = r * 2
    px_per_mm = diameter_px / QUARTER_DIAMETER_MM

    print(f"[Quarter] Detected at ({cx}, {cy}), radius={r}px")
    print(f"[Quarter] Scale: {px_per_mm:.2f} px/mm  ({px_per_mm*1000:.1f} px/m)")

    if debug:
        vis = image_bgr.copy()
        cv2.circle(vis, (cx, cy), r, (0, 255, 0), 3)
        cv2.circle(vis, (cx, cy), 3, (0, 0, 255), -1)
        cv2.putText(vis, f"{diameter_px}px = 24.26mm", (cx - 60, cy - r - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 0), 2)
        cv2.imshow("Quarter Detection", vis)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    return px_per_mm


# ─────────────────────────────────────────────────────────────
# STEP 2: PARTICLE SEGMENTATION
# ─────────────────────────────────────────────────────────────

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
    """
    results = model.predict(image_bgr, conf=conf_threshold, verbose=False, device=get_device())
    particles = []

    if results[0].masks is None:
        print("[WARNING] No particles detected.")
        return particles

    masks = results[0].masks.data.cpu().numpy()   # (N, H, W)
    boxes = results[0].boxes.xyxy.cpu().numpy()   # (N, 4)

    for i, (mask, box) in enumerate(zip(masks, boxes)):
        # Resize mask to match original image size
        mask_resized = cv2.resize(
            mask, (image_bgr.shape[1], image_bgr.shape[0]),
            interpolation=cv2.INTER_NEAREST
        ).astype(np.uint8)

        area_px = int(mask_resized.sum())
        if area_px < 10:   # skip noise
            continue

        # Equivalent circular diameter: d = 2 * sqrt(A / pi)
        diameter_px = 2 * np.sqrt(area_px / np.pi)

        particles.append({
            "mask": mask_resized,
            "area_px": area_px,
            "diameter_px": diameter_px,
            "bbox": box.astype(int).tolist(),
        })

    print(f"[Segmentation] {len(particles)} particles detected.")

    if debug and particles:
        vis = image_bgr.copy()
        for p in particles:
            color = tuple(np.random.randint(100, 255, 3).tolist())
            vis[p["mask"] == 1] = (
                vis[p["mask"] == 1] * 0.5 + np.array(color) * 0.5
            ).astype(np.uint8)
        cv2.imshow("Particle Segmentation", vis)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    return particles


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

def compute_psd(diameters_um: list[float]) -> dict:
    """
    Compute standard PSD statistics from a list of particle diameters (µm).

    Returns dict with D10, D50, D90, mean, std, and histogram arrays.
    """
    if not diameters_um:
        return {}

    arr = np.array(diameters_um)

    psd = {
        "n_particles": len(arr),
        "D10": float(np.percentile(arr, 10)),
        "D50": float(np.percentile(arr, 50)),
        "D90": float(np.percentile(arr, 90)),
        "mean_um": float(arr.mean()),
        "std_um": float(arr.std()),
        "min_um": float(arr.min()),
        "max_um": float(arr.max()),
        "span": float((np.percentile(arr, 90) - np.percentile(arr, 10))
                      / np.percentile(arr, 50)),  # (D90-D10)/D50
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
    model_path: str = "yolov8n-seg.pt",   # swap for your fine-tuned weights
    conf: float = 0.25,
    debug: bool = False,
    save_plot: str | None = None,
) -> dict:
    """
    Full pipeline: image → PSD + grind classification.

    Args:
        image_path:  Path to input image (JPG/PNG).
        model_path:  YOLOv8-Seg weights. Use pretrained for testing,
                     fine-tuned weights for production.
        conf:        Detection confidence threshold.
        debug:       Show intermediate visualizations.
        save_plot:   If set, saves PSD plot to this path.

    Returns:
        dict with psd stats + grind category.
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
    px_per_mm = detect_quarter(image, debug=debug)
    if px_per_mm is None:
        raise RuntimeError(
            "Quarter not detected. Ensure a US quarter is visible on white paper."
        )

    # Step 2: Particle segmentation
    model = YOLO(model_path)
    model.to(get_device())
    particles = segment_particles(image, model, conf_threshold=conf, debug=debug)
    if not particles:
        raise RuntimeError("No particles detected. Check model or image quality.")

    # Step 3: Convert to microns
    diameters_um = compute_diameters_um(particles, px_per_mm)

    # Step 4: PSD
    psd = compute_psd(diameters_um)

    # Step 5: Classify
    grind_category = classify_grind(psd["D50"])
    psd["grind_category"] = grind_category
    psd["px_per_mm"] = px_per_mm

    # Report
    print(f"\n{'─'*40}")
    print(f"  Particles detected : {psd['n_particles']}")
    print(f"  Scale              : {px_per_mm:.2f} px/mm")
    print(f"  D10                : {psd['D10']:.1f} µm")
    print(f"  D50 (median)       : {psd['D50']:.1f} µm")
    print(f"  D90                : {psd['D90']:.1f} µm")
    print(f"  Span (D90-D10)/D50 : {psd['span']:.2f}")
    print(f"  Grind category     : {grind_category.upper()}")
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
    infer.add_argument("--model", default="yolov8n-seg.pt", help="Model weights")
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
