#!/bin/bash
set -e

MODEL_FILE="best.pt"
R2_PREFIX="${R2_MODEL_PREFIX:-models}"

echo "[start] Checking for model weights..."

if [ -f "$MODEL_FILE" ]; then
    echo "[start] $MODEL_FILE already present, skipping download."
else
    echo "[start] Downloading from R2..."
    python r2_sync.py --prefix "$R2_PREFIX" --bucket "$R2_BUCKET_NAME" download --dest .
    find . -name "best.pt" | head -1 | xargs -I{} cp {} ./best.pt
    echo "[start] Model ready."
fi

echo "[start] Starting API server..."
exec uvicorn api_server:app --host 0.0.0.0 --port "${PORT:-8000}"
