"""
modal_app.py — Deploy TrueGrind FastAPI backend on Modal.

Deploy:
    python3 -m modal deploy modal_app.py

Check logs:
    python3 -m modal app logs truegrind-api
"""

import os
import modal

# ── Image: install all dependencies (CPU-only torch to keep size down) ──
image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("libgl1", "libglib2.0-0", "libheif-dev")
    .pip_install(
        "torch==2.1.0",
        "torchvision==0.16.0",
    )
    .pip_install(
        "ultralytics==8.4.33",
        "opencv-python-headless",
        "numpy<2",
        "scipy",
        "boto3",
        "python-dotenv",
        "fastapi",
        "uvicorn",
        "pydantic",
        "requests",
        "tqdm",
        "python-multipart",
        "Pillow",
        "pillow-heif",
    )
    .add_local_dir(".", remote_path="/root", ignore=[".venv", "__pycache__", ".git", "runs", "data", "ds", "models"])
)

# ── App ──────────────────────────────────────────────────────────────────
app = modal.App("truegrind-api", image=image)

# ── Secrets: store R2 credentials in Modal, not in code ─────────────────
# Set these once via: python3 -m modal secret create truegrind-secrets \
#   R2_ACCESS_KEY_ID=... R2_SECRET_ACCESS_KEY=... \
#   R2_ACCOUNT_ID=... R2_BUCKET_NAME=truegrind \
#   R2_MODEL_PREFIX=models/models MODEL_PATH=best.pt
secrets = [modal.Secret.from_name("truegrind-secrets")]

# ── Volume: cache the model weights so we don't re-download every cold start
volume = modal.Volume.from_name("truegrind-model-cache", create_if_missing=True)
MODEL_DIR = "/model-cache"

@app.function(
    secrets=secrets,
    volumes={MODEL_DIR: volume},
    cpu=2,
    memory=4096,
    gpu="T4",  # cheapest Modal GPU, plenty for inference
    timeout=120,
    scaledown_window=300,
)
@modal.asgi_app()
def fastapi_app():
    import sys
    import os
    from pathlib import Path

    # Download model from R2 if not already cached
    model_path = Path(MODEL_DIR) / "best.pt"
    if not model_path.exists():
        print("[Modal] Downloading best.pt from R2...")
        import boto3
        from botocore.config import Config

        account_id = os.environ["R2_ACCOUNT_ID"]
        bucket = os.environ["R2_BUCKET_NAME"]
        prefix = os.environ.get("R2_MODEL_PREFIX", "models/models")

        client = boto3.client(
            "s3",
            endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
            region_name="auto",
            config=Config(retries={"max_attempts": 3}),
        )
        model_path.parent.mkdir(parents=True, exist_ok=True)
        client.download_file(bucket, f"{prefix}/best.pt", str(model_path))
        volume.commit()
        print(f"[Modal] Model downloaded to {model_path}")
    else:
        print(f"[Modal] Model already cached at {model_path}")

    # Point MODEL_PATH to cached location
    os.environ["MODEL_PATH"] = str(model_path)

    # Add project root to path so imports work
    sys.path.insert(0, "/root")

    # Import and return the FastAPI app
    from api_server import app as fastapi_app
    return fastapi_app
