# True Grind — Complete Project Context

> This document contains everything an LLM needs to understand and continue development on the True Grind coffee grind analysis application. Last updated: 2026-04-11.

---

## 1. Project Overview

**True Grind** is a mobile-first web app that photographs coffee grounds, measures individual particle sizes using computer vision, and provides grind adjustment recommendations to improve coffee brewing. Think of it as a digital particle-size analyzer for home coffee enthusiasts.

### Core Workflow
1. User spreads coffee grounds on white paper with a US quarter for scale
2. User takes a photo → uploads to app
3. YOLOv8-Seg instance segmentation model detects individual particles
4. Quarter detection (Hough Circle Transform) establishes px→mm scale
5. Particle Size Distribution (PSD) computed: D10, D50, D90, span
6. Grind classification: espresso / moka_pot / filter / french_press / coarse
7. Recommendation engine suggests grinder dial adjustments based on D50 + taste feedback

### Tech Stack
- **Backend:** Python 3.12, FastAPI, Uvicorn
- **ML:** Ultralytics YOLOv8s-seg (instance segmentation), OpenCV, PyTorch
- **Frontend:** SvelteKit (Svelte 5), Vite
- **Dataset Management:** Roboflow
- **Package Manager:** `uv` (Python), `npm` (frontend)
- **Cloud Storage:** Cloudflare R2 (for dataset sync)

---

## 2. Project Structure

```
truegrind-final/
├── api_server.py              # FastAPI backend (main entry point for API)
├── grind_pipeline.py          # Core vision pipeline (768 lines)
├── best.pt                    # Fine-tuned YOLOv8s-seg model (23.9MB, 3-class)
├── best_v1_old.pt             # Old model backup (6.8MB, v1 no augmentation)
├── yolov8n-seg.pt             # Pretrained nano model (7MB, unused)
├── main.py                    # Simple entry point
├── bootstrap.py               # Project setup script
├── roboflow_prep.py           # Dataset download + merge from Roboflow
├── r2_sync.py                 # Cloudflare R2 dataset sync
├── test_recommendation.py     # Recommendation engine unit tests
├── .env                       # API keys (Roboflow, R2)
├── pyproject.toml             # Python project config (uv)
│
├── recommendation/            # Grind adjustment recommendation engine
│   ├── __init__.py
│   ├── recommendation_engine.py  # Rule-based + LLM-augmented recommendations
│   ├── rules_filter.json         # Brew method rules (ideal D50 ranges, temps, etc.)
│   └── taste_parser.py           # NLP taste note parser (sour/bitter/balanced)
│
├── frontend/                  # SvelteKit web app
│   ├── src/
│   │   ├── routes/
│   │   │   ├── +page.svelte           # Main analyze page (photo upload + results)
│   │   │   ├── +layout.svelte         # App shell with bottom nav
│   │   │   ├── journal/+page.svelte   # Brew journal (placeholder)
│   │   │   ├── community/+page.svelte # Community feed (placeholder)
│   │   │   └── profile/+page.svelte   # User profile (placeholder)
│   │   └── app.html
│   ├── package.json
│   └── vite.config.js
│
├── docs/                      # Project documentation
│   ├── true-grind-consolidated.md
│   └── true_grind_llm_coding_handoff.md
│
├── data/                      # Training data (gitignored)
├── raw_datasets/              # Roboflow downloads (gitignored)
└── runs/                      # Training runs (gitignored)
```

---

## 3. ML Model — YOLOv8s-seg (3-Class)

### 3.1 Model Details

| Property | Value |
|---|---|
| **Architecture** | YOLOv8s-seg (small, instance segmentation) |
| **Parameters** | 11,791,257 (11.8M) |
| **File** | `best.pt` (23.9 MB) |
| **Input size** | 640×640 (internal resize) |
| **Classes** | 3: `clump` (0), `coffee-grounds-dataset` (1), `silverskin` (2) |
| **Training** | Google Colab, Tesla T4, 104 epochs (early stopped at patience=40) |

### 3.2 Training Dataset (Roboflow)

- **Workspace:** `moonwons-workspace`
- **Project:** `coffee-grounds-dataset`
- **API Key:** `3kOJVCSFbkRtxm90viTA`
- **Version 1:** 13 images, no augmentation, 384×384
- **Version 2 (current):** 29 images (3× augmentation from 13 originals), 640×640
  - Train: 24 images (83%)
  - Validation: 3 images (10%)
  - Test: 2 images (7%)

**Augmentations applied (Roboflow):**
- Flip: Horizontal + Vertical
- 90° Rotate: Clockwise, Counter-Clockwise, Upside Down
- Rotation: ±15°
- Brightness: ±15%
- Blur: Up to 2.5px
- Noise: Up to 0.1% of pixels

**Annotation counts (original 13 images):**
| Class | Annotations | Notes |
|---|---|---|
| `coffee-grounds-dataset` | 877 | Well-represented, model learns this well |
| `silverskin` | 19 | Under-represented, model struggles |
| `clump` | 7 | Under-represented, model struggles |

### 3.3 Training Results

| Metric | V1 (no augment) | V2 (3× augment) | Change |
|---|---|---|---|
| **Mask mAP50** | 0.351 | **0.538** | **+53%** |
| **Box mAP50** | 0.497 | **0.668** | **+34%** |
| **Box mAP50-95** | 0.218 | **0.248** | +14% |
| **Precision** | 0.565 | **0.668** | +18% |
| **Recall** | 0.517 | **0.573** | +11% |

**Per-class (V2):** Only `coffee-grounds-dataset` learned well. `clump` and `silverskin` need more labeled examples (20-30+ images with dedicated annotations).

### 3.4 Training Hyperparameters (V2)

```python
model.train(
    data=f"{dataset.location}/data.yaml",
    epochs=200, imgsz=640, batch=16, patience=40,
    lr0=0.01, lrf=0.01,
    name="coffee-grind-seg-v2",
    flipud=0.5, fliplr=0.5, mosaic=1.0, mixup=0.15,
    copy_paste=0.3, degrees=15, translate=0.2, scale=0.5,
    hsv_h=0.015, hsv_s=0.7, hsv_v=0.4,
    perspective=0.001, erasing=0.3,
)
```

### 3.5 How to Retrain

1. Label more images in Roboflow (especially clumps + silverskin)
2. Create a new version with augmentation
3. Open Google Colab with a T4 GPU
4. Run:
```python
!pip install -q ultralytics roboflow
from roboflow import Roboflow
rf = Roboflow(api_key="3kOJVCSFbkRtxm90viTA")
project = rf.workspace("moonwons-workspace").project("coffee-grounds-dataset")
version = project.version(N)  # N = new version number
dataset = version.download("yolov8")

from ultralytics import YOLO
model = YOLO("yolov8s-seg.pt")
results = model.train(data=f"{dataset.location}/data.yaml", epochs=200, imgsz=640, batch=16, patience=40)
```
5. Download `best.pt` and replace in project root

---

## 4. Vision Pipeline (`grind_pipeline.py`)

### 4.1 Pipeline Steps

```
Image → Quarter Detection → Segmentation → Classification → Cluster Split → PSD → Grind Category
```

1. **Quarter Detection** (`detect_quarter()`): Hough Circle Transform finds a US quarter (24.26mm diameter), computes `px_per_mm` scale factor.

2. **Particle Segmentation** (`segment_particles()`): YOLOv8-Seg runs inference. Returns per-detection: mask, area_px, diameter_px, bbox, **class_id**, **class_name**.

3. **Detection Classification** (`classify_detections()`): Separates detections into three buckets:
   - `coffee-grounds-dataset` (class_id=1) → Used for PSD measurement
   - `silverskin` (class_id=2) → Excluded entirely (chaff, not extractable coffee)
   - `clump` (class_id=0) → Flagged with warnings:
     - `clump_ratio > 5%` → mild warning ("results may be less accurate")
     - `clump_ratio > 15%` → retake warning ("spread grounds more thinly")

4. **Cluster Splitting** (`split_clusters()`): Watershed segmentation splits oversized ground detections (>2mm equivalent diameter) into individual particles.

5. **PSD Computation** (`compute_psd()`): From ground-only particle diameters in µm:
   - D10, D50, D90, mean, std, span
   - Distribution breakdown: fines (<200µm), uniform, boulders (>1000µm)
   - Bimodal flag (high fines AND boulders = grinder issue)
   - Uniformity rating: good / moderate / poor

6. **Grind Classification** (`classify_grind()`): Maps D50 to category:
   - espresso: 0-400µm
   - moka_pot: 400-500µm
   - filter: 500-700µm
   - french_press: 700-900µm
   - coarse: 900µm+

### 4.2 Key Constants

```python
CLASS_NAMES = {0: "clump", 1: "coffee-grounds-dataset", 2: "silverskin"}
QUARTER_DIAMETER_MM = 24.26
CLUMP_WARN_RATIO = 0.05      # >5% → mild warning
CLUMP_RETAKE_RATIO = 0.15    # >15% → retake photo
FINES_THRESHOLD_UM = 200
BOULDER_THRESHOLD_UM = 1000
```

### 4.3 CLI Usage

```bash
# Analyze an image
uv run python grind_pipeline.py infer path/to/photo.jpg --model best.pt

# Train (using local data.yaml)
uv run python grind_pipeline.py train --data-yaml data/data.yaml --epochs 50
```

---

## 5. API Server (`api_server.py`)

### 5.1 Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/health` | Health check. Returns `{"status":"ok","model":"best.pt"}` |
| `POST` | `/api/analyze` | Upload photo → PSD analysis + 3-class breakdown |
| `POST` | `/api/recommend` | Submit D50 + taste notes → grinder adjustment advice |
| `GET` | `/api/brew-methods` | List brew methods with ideal D50 ranges |

### 5.2 POST /api/analyze Response

```json
{
  "success": true,
  "psd": {
    "n_particles": 85,
    "D10": 320.5, "D50": 580.2, "D90": 1050.3,
    "mean_um": 620.1, "span": 1.26,
    "fines_pct": 8.2, "uniform_pct": 72.1, "boulders_pct": 19.7,
    "bimodal_flag": false, "uniformity": "moderate"
  },
  "grind_category": "filter",
  "classification_message": "Your grind is well-suited for pour over...",
  "scale_px_per_mm": 18.63,
  "n_silverskin": 4,
  "n_clumps": 0,
  "clump_ratio": 0.0,
  "clump_warning": null
}
```

### 5.3 Performance Optimizations

- **Model warmup at startup**: Runs dummy inference on startup to compile MPS/CUDA graphs (~1.2s on subsequent starts)
- **Image downscaling**: `MAX_IMAGE_DIM = 2400` — phone photos (4032px) are downscaled to preserve speed while maintaining enough resolution for individual ground detection
- **Device caching**: `get_device()` only probes GPU once, caches result
- **Lazy model loading**: Model loaded once, reused across requests

### 5.4 Running the Server

```bash
cd truegrind-final
uv run uvicorn api_server:app --port 8000        # production
uv run uvicorn api_server:app --reload --port 8000  # development
```

---

## 6. Recommendation Engine (`recommendation/`)

### 6.1 How It Works

Rule-based system with optional LLM augmentation:

1. Compare user's D50 to ideal range for their brew method
2. If D50 is far off → suggest grinder dial adjustment (uses `fitted_slope` µm/step)
3. If D50 is close but taste is off:
   - Sour → suggest hotter water (+2°C)
   - Bitter → suggest cooler water (-2°C)
   - Balanced → "Keep this setting"
   - Mixed → "Diagnose evenness first"

### 6.2 Brew Method Rules (`rules_filter.json`)

Defines ideal ranges for: pour_over, espresso, french_press, aeropress, cold_brew, chemex, moka_pot. Each specifies:
- `ideal_d50_range` (µm)
- `ideal_water_temp_range` (°C)
- `ideal_extraction_time_range` (s)
- `filter_types`, `dose_ratios`

### 6.3 Taste Parser (`taste_parser.py`)

NLP module that converts free-text taste descriptions ("sour and underextracted") into structured tags (`["sour", "underextracted"]`). Supports optional OpenAI LLM-based parsing for complex descriptions.

### 6.4 Grinder Defaults

```python
FELLOW_ODE_DEFAULTS = {
    "fitted_slope": 50,       # µm per setting step
    "dial_range_min": 1,
    "dial_range_max": 11,
    "grinder_model": "Fellow Ode Brew Grinder Gen 2",
}
```

---

## 7. Frontend (SvelteKit)

### 7.1 Pages

| Route | Description | Status |
|---|---|---|
| `/` | Main analyze page — photo upload, PSD results display | ✅ Functional |
| `/journal` | Brew journal — log past brews | 🔲 Placeholder |
| `/community` | Community feed — shared analyses | 🔲 Placeholder |
| `/profile` | User profile | 🔲 Placeholder |

### 7.2 Main Page Features

- Photo upload via file picker or camera capture
- Supports JPG, PNG, HEIC (client-side HEIC→JPEG conversion)
- Shows "Connected" / "Offline" backend status indicator
- Displays results:
  - D50 with grind category label
  - D10 / D90 metrics
  - Particle count
  - Uniformity rating + span
  - Fines / uniform / boulders breakdown bars
  - Grind size reference guide

### 7.3 Running the Frontend

```bash
cd truegrind-final/frontend
npm run dev    # http://localhost:5173
```

---

## 8. Known Issues & Limitations

### 8.1 Model Accuracy
- **Clump and silverskin detection is unreliable** — only 7 and 19 annotations respectively. The model effectively only detects `coffee-grounds-dataset`. Need 20-30+ more images with these classes well-represented.
- **D50 values are ~1200-1400µm higher than expected** — the model may be segmenting clumps of grounds as single particles, inflating equivalent diameter. Root causes:
  - At downscaled resolutions, individual grounds are only ~11-18px across
  - The model was trained on 640×640 images where individual grounds are very small
  - Watershed splitting doesn't always catch all clusters

### 8.2 Performance
- First model load takes ~6-7s (MPS compilation). Subsequent requests: ~5-10s per photo.
- `MAX_IMAGE_DIM = 2400` is a tradeoff — lower = faster but less accurate; higher = more accurate but Hough Circle Transform becomes very slow.

### 8.3 Quarter Detection
- Requires the quarter to be on a light/white background
- Only detects US quarters (24.26mm diameter)
- Hough Circle Transform parameters are tuned for specific distance range; may fail on very close-up or very wide shots

---

## 9. Environment & Dependencies

### Python (managed by `uv`)
```
ultralytics, opencv-python-headless, numpy, matplotlib, scipy,
torch, torchvision, fastapi, uvicorn, python-dotenv, pydantic,
roboflow, pillow
```

### Node.js (frontend)
```
@sveltejs/kit, svelte, vite, heic2any (HEIC conversion)
```

### Environment Variables (`.env`)
```
ROBOFLOW_API_KEY=3kOJVCSFbkRtxm90viTA
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
R2_ACCOUNT_ID=...
R2_BUCKET_NAME=grind-dataset
```

---

## 10. Next Steps (Priority Order)

### High Priority
1. **Fix D50 overestimation** — investigate whether the model is merging grounds into larger blobs. Options:
   - Retrain with `yolov8n-seg` (nano) at higher resolution like 1024×1024
   - Add more training images with tighter individual-ground annotations
   - Make watershed splitting more aggressive (lower `max_particle_mm` threshold)
   - Try running inference at higher `imgsz` (e.g., `model.predict(img, imgsz=1024)`)

2. **Label more data** — add 20-30 more photos focusing on:
   - Varied lighting conditions
   - Different grind sizes (espresso through coarse)
   - More clump examples (>30 annotations needed)
   - More silverskin examples (>30 annotations needed)

3. **Retrain on expanded dataset** — use Google Colab with the same hyperparameters

### Medium Priority
4. **Frontend: display 3-class info** — show silverskin count and clump warnings in the UI
5. **Frontend: wire up recommendation** — add taste feedback form → call `/api/recommend` → show adjustment advice
6. **Frontend: build Journal page** — save past analyses with grinder settings

### Lower Priority
7. **Deploy to cloud** — host backend on a server so the app works outside localhost
8. **Add more grinder profiles** — support Baratza Encore, Comandante, etc. with specific `fitted_slope` values
9. **Continuous improvement** — collect user photos through the app to grow training dataset

---

## 11. Quick Start Commands

```bash
# Start backend
cd truegrind-final
uv run uvicorn api_server:app --port 8000

# Start frontend (separate terminal)
cd truegrind-final/frontend
npm run dev

# Test pipeline on an image
cd truegrind-final
uv run python grind_pipeline.py infer photo.jpg

# Test API
curl -X POST http://localhost:8000/api/analyze -F "file=@photo.jpg"

# Health check
curl http://localhost:8000/api/health
```
