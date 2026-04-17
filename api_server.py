"""
api_server.py — FastAPI backend for True Grind.

Endpoints:
    POST /api/analyze      → Upload photo, get PSD + classification
    POST /api/recommend    → Submit brew vars + taste notes, get adjustment advice
    GET  /api/brew-methods → List supported brew methods with ideal ranges
    GET  /api/health       → Health check

Run:
    uv run uvicorn api_server:app --reload --port 8000
"""

from __future__ import annotations

import os
import tempfile
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2
import numpy as np
from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
from pydantic import BaseModel
import io

from grind_pipeline import (
    detect_quarter,
    estimate_quarter_aspect_ratio,
    crop_around_quarter,
    segment_particles,
    classify_detections,
    split_clusters,
    compute_diameters_um,
    compute_psd,
    classify_grind,
    get_device,
    FINES_THRESHOLD_UM,
    BOULDER_THRESHOLD_UM,
)
from recommendation.recommendation_engine import (
    recommend_filter,
    classify_grind_message,
    load_rules,
)
from recommendation.taste_parser import parse_taste_notes

load_dotenv()

# ─── App setup ──────────────────────────────────────────────

app = FastAPI(
    title="True Grind API",
    description="Coffee grind analysis & recommendation engine",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Model loading (once at startup) ────────────────────────

MODEL_PATH = os.environ.get("MODEL_PATH", "best.pt")
MAX_IMAGE_DIM = 2400   # balance between resolution for ground detection and speed
_model = None


def get_model():
    """Lazy-load the YOLOv8-Seg model."""
    global _model
    if _model is None:
        from ultralytics import YOLO
        _model = YOLO(MODEL_PATH)
        _model.to(get_device())
        print(f"[API] Model loaded from {MODEL_PATH}")
    return _model


@app.on_event("startup")
def warmup_model():
    """Pre-load model and run a dummy inference to warm up MPS/CUDA."""
    import time
    t0 = time.time()
    model = get_model()
    # Dummy inference to trigger MPS/CUDA graph compilation
    dummy = np.zeros((640, 640, 3), dtype=np.uint8)
    model.predict(dummy, conf=0.5, verbose=False, device=get_device())
    print(f"[API] Model warmed up in {time.time() - t0:.1f}s")


def resize_for_speed(image: np.ndarray) -> tuple[np.ndarray, float]:
    """
    Downscale large images to MAX_IMAGE_DIM on the longest side.
    Returns (resized_image, scale_factor) where scale_factor lets
    us convert px_per_mm back to original image coordinates.
    """
    h, w = image.shape[:2]
    longest = max(h, w)
    if longest <= MAX_IMAGE_DIM:
        return image, 1.0
    scale = MAX_IMAGE_DIM / longest
    new_w, new_h = int(w * scale), int(h * scale)
    resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
    print(f"[Resize] {w}x{h} → {new_w}x{new_h} (scale={scale:.3f})")
    return resized, scale


def image_quality_checks(image: np.ndarray) -> list[dict]:
    """
    Run image-level quality checks (blur, contrast).
    Returns a list of warning dicts: {code, severity, message, tip}
    Called early — before quarter detection or segmentation.
    """
    warnings = []

    # 1. Blur detection via Laplacian variance
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    print(f"[Quality] Laplacian variance (blur): {lap_var:.1f}")
    if lap_var < 10:
        warnings.append({
            "code": "blurry",
            "severity": "error",
            "message": "Image appears very blurry",
            "tip": "Hold your phone steady or use a flat surface. Tap to focus on the grounds before shooting.",
        })

    # 2. Low contrast (poor lighting)
    contrast = gray.std()
    print(f"[Quality] Contrast (std): {contrast:.1f}")
    if contrast < 15:
        warnings.append({
            "code": "low_contrast",
            "severity": "warning",
            "message": "Low contrast — poor lighting detected",
            "tip": "Move to a well-lit area or use natural daylight. Avoid shadows over the grounds.",
        })

    return warnings


# ─── Fellow Ode defaults ────────────────────────────────────

FELLOW_ODE_DEFAULTS = {
    "fitted_slope": 102,      # calibrated: ~102 µm per step (275µm@1 → 1193µm@10)
    "dial_range_min": 1,
    "dial_range_max": 11,
    "grinder_model": "Fellow Ode Brew Grinder Gen 2",
}


# ─── Request/Response models ────────────────────────────────

class RecommendRequest(BaseModel):
    """Payload for the /recommend endpoint."""
    current_d50: float
    current_setting: float
    brew_method: str = "pour_over"
    taste_notes: str = ""
    taste_tags: Optional[List[str]] = None
    water_temp_c: Optional[float] = None
    extraction_time_s: Optional[float] = None
    filter_type: Optional[str] = None
    dose_g: Optional[float] = None
    water_g: Optional[float] = None
    num_pours: Optional[int] = None
    agitation_level: Optional[str] = None

    # Grinder overrides (defaults to Fellow Ode)
    fitted_slope: Optional[float] = None
    dial_range_min: Optional[float] = None
    dial_range_max: Optional[float] = None


# ─── Endpoints ──────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok", "model": MODEL_PATH}


@app.get("/api/brew-methods")
def get_brew_methods():
    """Return available brew methods with their ideal ranges."""
    rules = load_rules()
    methods = rules.get("brew_methods", {})
    return {"brew_methods": methods}


@app.post("/api/preflight")
async def preflight_check(file: UploadFile = File(...)):
    """
    Quick calibration check — runs quarter detection only (no YOLO).
    Returns px_per_mm and distance quality so the user can adjust before full analysis.
    ~0.1s response time.
    """
    contents = await file.read()
    image = None

    np_arr = np.frombuffer(contents, np.uint8)
    image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    if image is None:
        try:
            import pillow_heif
            pillow_heif.register_heif_opener()
            pil_img = Image.open(io.BytesIO(contents))
            pil_img = pil_img.convert('RGB')
            image = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        except Exception:
            return {"found": False, "quality": "decode_error", "message": "Could not decode image."}

    if image is None:
        return {"found": False, "quality": "decode_error", "message": "Could not decode image."}

    # Resize for speed (same as analyze)
    image, _ = resize_for_speed(image)

    px_per_mm, quarter_circle = detect_quarter(image)

    if px_per_mm is None:
        return {
            "found": False,
            "px_per_mm": None,
            "quality": "not_found",
            "message": "No quarter detected. Make sure a US quarter is fully visible.",
        }

    # Rate the calibration quality
    if px_per_mm < 18:
        quality = "too_far"
        message = f"Quarter too small ({px_per_mm:.0f} px/mm). Move closer."
    elif px_per_mm > 50:
        quality = "too_close"
        message = f"Quarter too large ({px_per_mm:.0f} px/mm). Move farther away."
    elif 22 <= px_per_mm <= 30:
        quality = "good"
        message = f"Great distance ({px_per_mm:.0f} px/mm) ✓"
    else:
        quality = "ok"
        message = f"Acceptable ({px_per_mm:.0f} px/mm). Ideal range is 22–30."

    return {
        "found": True,
        "px_per_mm": round(px_per_mm, 1),
        "quality": quality,
        "message": message,
    }


@app.post("/api/analyze")
async def analyze_photo(
    file: UploadFile = File(...),
    brew_method: str = "pour_over",
    tilt_angle_deg: float = 0.0,
):
    """
    Upload a photo of coffee grounds → get PSD analysis.

    Returns D50, distribution breakdown, classification message, etc.
    """
    # Read + decode image (supports HEIC, JPEG, PNG)
    contents = await file.read()
    filename = (file.filename or "").lower()
    image = None

    # Try standard cv2 decode first (JPEG, PNG, WebP, etc.)
    np_arr = np.frombuffer(contents, np.uint8)
    image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    # If cv2 failed, try pillow-heif (handles HEIC/HEIF regardless of extension)
    if image is None:
        try:
            import pillow_heif
            pillow_heif.register_heif_opener()
            pil_img = Image.open(io.BytesIO(contents))
            pil_img = pil_img.convert('RGB')
            image = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
            print(f"[Decode] Decoded via pillow-heif: {image.shape[1]}x{image.shape[0]}")
        except Exception as e:
            print(f"[Decode] pillow-heif also failed: {e}")
            image = None

    # If filename says HEIC but cv2 succeeded, still try pillow-heif for higher quality
    if image is not None and filename.endswith(('.heic', '.heif')):
        try:
            import pillow_heif
            pillow_heif.register_heif_opener()
            pil_img = Image.open(io.BytesIO(contents))
            pil_img = pil_img.convert('RGB')
            heif_image = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
            # Use HEIF decode if it produced a higher-res image
            if heif_image.shape[0] * heif_image.shape[1] >= image.shape[0] * image.shape[1]:
                image = heif_image
                print(f"[Decode] Using pillow-heif (higher res): {image.shape[1]}x{image.shape[0]}")
        except Exception:
            pass  # keep cv2 version

    if image is None:
        raise HTTPException(status_code=400, detail="Could not decode image. Send JPG, PNG, or HEIC.")

    try:
        # Downscale large phone photos for speed
        image, scale_factor = resize_for_speed(image)

        # Run early quality checks (blur, contrast) on every image
        early_warnings = image_quality_checks(image)

        # Step 1: Quarter detection (on resized image)
        px_per_mm, quarter_circle = detect_quarter(image)
        if px_per_mm is None:
            early_warnings.append({
                "code": "no_quarter",
                "severity": "error",
                "message": "No US quarter detected in the image",
                "tip": "Place a US quarter on the white paper next to your grounds. Make sure it's fully visible and not covered by grounds.",
            })
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "No quarter detected — see tips below to fix your photo.",
                    "quality_warnings": early_warnings,
                }
            )



        # Note: cropping was removed — it cut off too many particles.

        # Step 2: Particle segmentation (all 3 classes)
        model = get_model()
        all_detections = segment_particles(image, model, conf_threshold=0.25)
        if not all_detections:
            early_warnings.append({
                "code": "no_particles",
                "severity": "error",
                "message": "No coffee particles detected",
                "tip": "Make sure your grounds are spread on a white surface with good lighting. Dark surfaces make detection difficult.",
            })
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "No particles detected — see tips below.",
                    "quality_warnings": early_warnings,
                }
            )

        # Step 2b: Classify into grounds / silverskin / clumps
        detection_info = classify_detections(all_detections)
        grounds = detection_info["grounds"]

        if not grounds:
            early_warnings.append({
                "code": "only_clumps",
                "severity": "error",
                "message": "Only clumps detected — no individual particles found",
                "tip": "Break up the clumps by gently tapping or using a WDT tool. Spread the grounds more thinly on the paper.",
            })
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "No individual grounds detected — only clumps found.",
                    "quality_warnings": early_warnings,
                }
            )

        # Step 2c: Split oversized clusters into individual particles
        grounds = split_clusters(grounds, px_per_mm)

        # Step 3: Convert to microns (grounds only — silverskin excluded)
        diameters_um = compute_diameters_um(grounds, px_per_mm)

        # Step 3b: Tilt correction
        # Priority 1: IMU angle from frontend (camera captures on mobile)
        # Priority 2: Ellipse fallback for uploads (only if AR < 0.85 = severe tilt)
        import math
        tilt_correction = 1.0
        tilt_source = None

        if tilt_angle_deg > 1.0:
            # IMU data available — use directly
            cos_theta = math.cos(math.radians(tilt_angle_deg))
            if cos_theta > 0.01:  # safety clamp
                tilt_correction = 1.0 / math.sqrt(cos_theta)
                tilt_source = "imu"
                print(f"[Tilt] IMU: {tilt_angle_deg:.1f}° → correction={tilt_correction:.3f} "
                      f"(+{(tilt_correction - 1) * 100:.1f}%)")
        elif quarter_circle is not None:
            # No IMU — uploaded photo. Use conservative ellipse fallback.
            upload_ar = estimate_quarter_aspect_ratio(image, quarter_circle)
            if upload_ar < 0.85:  # severe tilt only — avoids false positives from engravings
                tilt_correction = 1.0 / math.sqrt(upload_ar)
                tilt_source = "ellipse"
                print(f"[Tilt] Ellipse fallback: AR={upload_ar:.3f} → correction={tilt_correction:.3f} "
                      f"(+{(tilt_correction - 1) * 100:.1f}%)")

        if tilt_correction > 1.001:
            diameters_um = [d * tilt_correction for d in diameters_um]
            correction_pct = (tilt_correction - 1) * 100
            if tilt_source == "imu" and tilt_angle_deg > 10:
                early_warnings.append({
                    "code": "camera_angle",
                    "severity": "warning",
                    "message": f"Camera tilted ~{tilt_angle_deg:.0f}°. Corrected +{correction_pct:.0f}%.",
                    "tip": "Results have been mathematically adjusted, but a flat overhead photo gives the most reliable measurements.",
                })
            elif tilt_source == "ellipse":
                early_warnings.append({
                    "code": "camera_angle",
                    "severity": "warning",
                    "message": f"Photo may have been taken at an angle. Corrected +{correction_pct:.0f}%.",
                    "tip": "For best accuracy, retake the photo holding your phone flat overhead.",
                })

        # DEBUG: Show diameter stats
        diameters_px = [p["diameter_px"] for p in grounds]
        print(f"[Debug] px_per_mm={px_per_mm:.2f} | particles={len(grounds)}")
        print(f"[Debug] diameter_px: min={min(diameters_px):.1f} median={sorted(diameters_px)[len(diameters_px)//2]:.1f} max={max(diameters_px):.1f}")
        print(f"[Debug] diameter_um: min={min(diameters_um):.0f} median={sorted(diameters_um)[len(diameters_um)//2]:.0f} max={max(diameters_um):.0f}")

        # Step 4: PSD
        psd = compute_psd(diameters_um)

        # Step 5: Classification
        grind_category = classify_grind(psd["D50"])
        classification_message = classify_grind_message(psd["D50"], brew_method=brew_method)

        # Step 6: Merge early quality checks with post-analysis checks
        # (early_warnings already has blur, contrast, quarter-cutoff)
        # Add particle count and clump ratio checks
        # Post-analysis accuracy warnings (non-blocking, shown on results page)

        # Calibration check: if px_per_mm is unusually low, the quarter may be
        # partially visible or detected wrong (normal range ~15-35 for phone photos)
        if px_per_mm < 18:
            early_warnings.append({
                "code": "low_calibration",
                "severity": "warning",
                "message": f"Low calibration ({px_per_mm:.1f} px/mm) — quarter may be too far or partially visible",
                "tip": "Move closer so the quarter fills ~¼ of the frame width, and ensure it's fully visible.",
            })
        elif px_per_mm > 50:
            early_warnings.append({
                "code": "high_calibration",
                "severity": "warning",
                "message": f"High calibration ({px_per_mm:.1f} px/mm) — quarter may be detected incorrectly",
                "tip": "A small bright object may have been mistaken for the quarter. Ensure a real US quarter is in the frame.",
            })

        if psd["n_particles"] < 15:
            early_warnings.append({
                "code": "few_particles",
                "severity": "warning",
                "message": f"Only {psd['n_particles']} particles detected — results may not be representative",
                "tip": "Spread more grounds on the paper for a better sample (aim for 50+ particles).",
            })
        if detection_info["clump_ratio"] > 0.3:
            early_warnings.append({
                "code": "excessive_clumping",
                "severity": "warning",
                "message": f"High clump ratio ({detection_info['clump_ratio']:.0%}) — many grounds are stuck together",
                "tip": "Break up clumps before photographing for more accurate particle sizing.",
            })
        quality_warnings = early_warnings

        return {
            "success": True,
            "psd": {
                "n_particles": psd["n_particles"],
                "D10": round(psd["D10"], 1),
                "D50": round(psd["D50"], 1),
                "D90": round(psd["D90"], 1),
                "mean_um": round(psd["mean_um"], 1),
                "span": round(psd["span"], 2),
                "fines_pct": psd["fines_pct"],
                "uniform_pct": psd["uniform_pct"],
                "boulders_pct": psd["boulders_pct"],
                "bimodal_flag": psd["bimodal_flag"],
                "uniformity": psd["uniformity"],
            },
            "grind_category": grind_category,
            "classification_message": classification_message,
            "scale_px_per_mm": round(px_per_mm, 2),
            # 3-class breakdown
            "n_silverskin": detection_info["n_silverskin"],
            "n_clumps": len(detection_info["clumps"]),
            "clump_ratio": round(detection_info["clump_ratio"], 3),
            "clump_warning": detection_info["clump_warning"],
            # Image quality
            "quality_warnings": quality_warnings,
        }

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@app.post("/api/recommend")
def get_recommendation(req: RecommendRequest):
    """
    Submit brew variables + taste feedback → get adjustment recommendation.
    """
    # Parse taste notes if tags not provided directly
    if req.taste_tags:
        tags = req.taste_tags
    elif req.taste_notes:
        tags = parse_taste_notes(req.taste_notes, use_llm=True)
    else:
        tags = []

    # Build recommendation payload
    payload: Dict[str, Any] = {
        "current_d50": req.current_d50,
        "current_setting": req.current_setting,
        "fitted_slope": req.fitted_slope or FELLOW_ODE_DEFAULTS["fitted_slope"],
        "dial_range_min": req.dial_range_min or FELLOW_ODE_DEFAULTS["dial_range_min"],
        "dial_range_max": req.dial_range_max or FELLOW_ODE_DEFAULTS["dial_range_max"],
        "taste_feedback": tags,
        "brew_method": req.brew_method,
    }

    # Add optional brew variables
    if req.water_temp_c is not None:
        payload["water_temp_c"] = req.water_temp_c
    if req.extraction_time_s is not None:
        payload["extraction_time_s"] = req.extraction_time_s
    if req.filter_type is not None:
        payload["filter_type"] = req.filter_type
    if req.dose_g is not None:
        payload["dose_g"] = req.dose_g
    if req.water_g is not None:
        payload["water_g"] = req.water_g
    if req.num_pours is not None:
        payload["num_pours"] = req.num_pours
    if req.agitation_level is not None:
        payload["agitation_level"] = req.agitation_level

    try:
        result = recommend_filter(payload)
        result["parsed_tags"] = tags
        return {"success": True, "recommendation": result}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Recommendation failed: {str(e)}")


# ─── Entry point ─────────────────────────────────────────────

def run():
    """CLI entrypoint: `uv run api`"""
    import uvicorn
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    run()
