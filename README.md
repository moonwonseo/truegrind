# TrueGrind — Coffee Grind Size Analysis

Measures coffee particle size distribution from a photo using a US quarter as a calibration scale. Detects the quarter → computes px/mm scale → segments particles with YOLOv8-Seg → outputs D10/D50/D90 and grind classification (espresso → coarse) → recommends grinder adjustment.

---

## Quickstart

```bash
# 1. Install dependencies
uv sync

# 2. Set your Roboflow API key in .env
cp .env.example .env
# Edit .env and add your ROBOFLOW_API_KEY

# 3. Download datasets + train
uv run grind train

# 4. Run inference on a photo
uv run grind infer photo.jpg --model runs/segment/.../best.pt
```

---

## How It Works

1. **Quarter detection** — Hough Circle Transform finds the quarter, computes `px/mm`
2. **Particle segmentation** — YOLOv8-Seg segments each particle with polygon masks
3. **Micron conversion** — `diameter_µm = (diameter_px / px_per_mm) × 1000`
4. **PSD stats** — D10, D50, D90, span `(D90−D10)/D50`, mean, std
5. **Grind classification** — rule-based from D50 thresholds
6. **Recommendation** — deterministic engine: adjusts grinder dial based on D50 vs target

---

## Commands

```bash
# Train — downloads data automatically if data/ is missing
uv run grind train
uv run grind train --epochs 100 --weights yolov8s-seg.pt

# Inference
uv run grind infer photo.jpg --model runs/segment/.../best.pt
uv run grind infer photo.jpg --model best.pt --save-plot psd.png

# Test recommendation engine
python3 test_recommendation.py

# R2 dataset sync (requires credentials)
uv run r2-sync upload
uv run r2-sync download --dest ds
uv run r2-sync list
```

---

## Project Structure

```
truegrind-final/
├── grind_pipeline.py          # Core vision pipeline + CLI
├── roboflow_prep.py           # Dataset download, merge, remap to 'particle'
├── r2_sync.py                 # Upload/download ↔ Cloudflare R2
├── test_recommendation.py     # Recommendation engine smoke tests
├── recommendation/            # Deterministic grind recommendation engine
│   ├── __init__.py
│   ├── recommendation_engine.py
│   ├── rules_filter.json
│   └── README.md
├── docs/                      # Product docs + grinder reference charts
│   ├── true-grind-consolidated.md
│   ├── true_grind_llm_coding_handoff.md
│   └── grind_charts/
├── frontend/                  # SvelteKit mobile app scaffold
├── pyproject.toml             # Dependencies + CLI entrypoints
├── .env.example               # Credential template
├── data/                      # Merged training dataset (auto-built, gitignored)
├── raw_datasets/              # Roboflow downloads (gitignored)
└── runs/                      # Training outputs (gitignored)
```

---

## Training Datasets (pre-training)

| Dataset | Type | Images |
|---|---|---|
| grain-3z0bc v11 | Rice/corn/wheat grains | ~190 |
| particle-segmentation-v2 v12 | Small particles | ~50 |
| seed-instance-segmentation v5 | Seeds | ~245 |
| coffee-bean-ztxe3 v2 | Coffee beans | ~145 |
| rice-grain-segmentation v8 | Rice grains | ~104 |

**Total: ~730 images** for pre-training. Fine-tune on your own coffee photos for best results.

---

## Grinder

Primary development grinder: **Fellow Ode Brew Grinder Gen 2**

## Grind Classification (D50 thresholds)

| Category | D50 |
|---|---|
| Espresso | < 400 µm |
| Moka pot | 400–500 µm |
| Filter | 500–700 µm |
| French press | 700–900 µm |
| Coarse | > 900 µm |

---

## Device Support

Auto-detected: **CUDA → MPS → CPU**

| Machine | Device |
|---|---|
| Mac (Apple Silicon) | MPS |
| Linux/Windows + NVIDIA | CUDA |
| Anything else | CPU |

---

## `.env` Credentials

| Variable | Where to find it | Required for |
|---|---|---|
| `ROBOFLOW_API_KEY` | [app.roboflow.com](https://app.roboflow.com) → Settings → API | Training data download |
| `R2_ACCESS_KEY_ID` | Cloudflare → R2 → API Tokens | R2 sync |
| `R2_SECRET_ACCESS_KEY` | Same token screen | R2 sync |
| `R2_ACCOUNT_ID` | Cloudflare dashboard | R2 sync |
| `R2_BUCKET_NAME` | Your R2 bucket name | R2 sync |
