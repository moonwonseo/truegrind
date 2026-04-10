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
from pydantic import BaseModel

from grind_pipeline import (
    detect_quarter,
    segment_particles,
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
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Model loading (once at startup) ────────────────────────

MODEL_PATH = os.environ.get("MODEL_PATH", "best.pt")
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


# ─── Fellow Ode defaults ────────────────────────────────────

FELLOW_ODE_DEFAULTS = {
    "fitted_slope": 50,       # estimated µm per setting step
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


@app.post("/api/analyze")
async def analyze_photo(
    file: UploadFile = File(...),
    brew_method: str = "pour_over",
):
    """
    Upload a photo of coffee grounds → get PSD analysis.

    Returns D50, distribution breakdown, classification message, etc.
    """
    # Read + decode image
    contents = await file.read()
    np_arr = np.frombuffer(contents, np.uint8)
    image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    if image is None:
        raise HTTPException(status_code=400, detail="Could not decode image. Send JPG or PNG.")

    try:
        # Step 1: Quarter detection
        px_per_mm = detect_quarter(image)
        if px_per_mm is None:
            raise HTTPException(
                status_code=422,
                detail="No quarter detected. Place a US quarter on white paper next to your grounds."
            )

        # Step 2: Particle segmentation
        model = get_model()
        particles = segment_particles(image, model, conf_threshold=0.25)
        if not particles:
            raise HTTPException(
                status_code=422,
                detail="No particles detected. Make sure grounds are spread on a white surface."
            )

        # Step 3: Convert to microns
        diameters_um = compute_diameters_um(particles, px_per_mm)

        # Step 4: PSD
        psd = compute_psd(diameters_um)

        # Step 5: Classification
        grind_category = classify_grind(psd["D50"])
        classification_message = classify_grind_message(psd["D50"], brew_method=brew_method)

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
