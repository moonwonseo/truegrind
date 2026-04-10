"""
r2_sync.py — Upload/download datasets to/from Cloudflare R2
=============================================================

# Authenticated (requires R2 credentials in .env)
uv run r2-sync upload                        # upload ds/ → R2
uv run r2-sync upload --src data --prefix data  # upload prepared data/ → R2
uv run r2-sync download --dest ds            # download ds/ from R2
uv run r2-sync download --prefix data --dest data  # download data/ from R2
uv run r2-sync list

# Public download (no credentials needed — requires R2_PUBLIC_URL in .env)
# Anyone can run this to pull the prepared training dataset:
uv run r2-sync download --prefix data --dest data

If R2_PUBLIC_URL is set (e.g. https://pub-xxx.r2.dev), downloads use plain
HTTPS and require no credentials. Uploads always require credentials.

Enable public access: Cloudflare → R2 → your bucket → Settings → Public Access
"""

import os
import sys
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import boto3
import requests
from botocore.config import Config
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from tqdm import tqdm

# ─────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────

load_dotenv()

def _require(key: str) -> str:
    val = os.getenv(key)
    if not val:
        sys.exit(
            f"[ERROR] Missing env var: {key}\n"
            f"        Copy .env.example → .env and fill in your credentials."
        )
    return val


def get_client():
    account_id = _require("R2_ACCOUNT_ID")
    endpoint = os.getenv(
        "R2_ENDPOINT_URL",
        f"https://{account_id}.r2.cloudflarestorage.com"
    )
    # Expand ${R2_ACCOUNT_ID} if the user left the template value
    endpoint = endpoint.replace("${R2_ACCOUNT_ID}", account_id)

    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=_require("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=_require("R2_SECRET_ACCESS_KEY"),
        region_name="auto",
        config=Config(
            retries={"max_attempts": 5, "mode": "adaptive"},
            max_pool_connections=20,
        ),
    )


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def list_remote_keys(client, bucket: str, prefix: str) -> dict[str, str]:
    """Return {key: etag} for every object under prefix."""
    keys = {}
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            keys[obj["Key"]] = obj["ETag"].strip('"')
    return keys


def local_files(src: Path, prefix: str) -> list[tuple[Path, str]]:
    """
    Walk src directory, return list of (local_path, r2_key) pairs.
    Directory structure under src/ is preserved under prefix/.
    """
    pairs = []
    for f in sorted(src.rglob("*")):
        if f.is_file():
            rel = f.relative_to(src.parent)   # keeps "ds/img/foo.png"
            r2_key = f"{prefix}/{rel}".replace("\\", "/") if prefix else str(rel)
            # Normalise double slashes
            r2_key = "/".join(p for p in r2_key.split("/") if p)
            pairs.append((f, r2_key))
    return pairs


# ─────────────────────────────────────────────────────────────
# Upload
# ─────────────────────────────────────────────────────────────

def upload(src: Path, bucket: str, prefix: str, dry_run: bool, workers: int):
    client = get_client()

    print(f"[Upload] Scanning {src} …")
    all_files = local_files(src, prefix)
    print(f"[Upload] {len(all_files)} local files found")

    print(f"[Upload] Fetching remote index …")
    remote = list_remote_keys(client, bucket, prefix)
    print(f"[Upload] {len(remote)} objects already in bucket")

    # Only upload files not yet present (skip by key existence)
    to_upload = [(p, k) for p, k in all_files if k not in remote]
    print(f"[Upload] {len(to_upload)} files to upload  "
          f"({len(all_files) - len(to_upload)} already synced)")

    if dry_run:
        for _, k in to_upload:
            print(f"  would upload → {k}")
        return

    if not to_upload:
        print("[Upload] Nothing to do.")
        return

    failed = []

    def _upload_one(args):
        local_path, key = args
        try:
            client.upload_file(
                str(local_path), bucket, key,
                ExtraArgs={"ContentType": _content_type(local_path)},
            )
            return key, None
        except ClientError as e:
            return key, str(e)

    with tqdm(total=len(to_upload), unit="file", desc="Uploading") as bar:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_upload_one, item): item for item in to_upload}
            for fut in as_completed(futures):
                key, err = fut.result()
                if err:
                    failed.append((key, err))
                bar.update(1)

    if failed:
        print(f"\n[Upload] {len(failed)} FAILED:")
        for k, e in failed:
            print(f"  {k}: {e}")
        sys.exit(1)
    else:
        print(f"[Upload] Done. {len(to_upload)} files uploaded to "
              f"s3://{bucket}/{prefix}/")


# ─────────────────────────────────────────────────────────────
# Download
# ─────────────────────────────────────────────────────────────

def download(bucket: str, prefix: str, dest: Path, workers: int):
    client = get_client()

    print(f"[Download] Fetching remote index under '{prefix}/' …")
    remote = list_remote_keys(client, bucket, prefix)
    print(f"[Download] {len(remote)} objects found")

    if not remote:
        print("[Download] Nothing to download.")
        return

    failed = []

    def _download_one(key: str):
        # Strip the top-level prefix so files land in dest/img/… not dest/ds/img/…
        rel = key[len(prefix):].lstrip("/") if key.startswith(prefix) else key
        local = dest / rel
        local.parent.mkdir(parents=True, exist_ok=True)
        try:
            client.download_file(bucket, key, str(local))
            return key, None
        except ClientError as e:
            return key, str(e)

    with tqdm(total=len(remote), unit="file", desc="Downloading") as bar:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_download_one, k): k for k in remote}
            for fut in as_completed(futures):
                key, err = fut.result()
                if err:
                    failed.append((key, err))
                bar.update(1)

    if failed:
        print(f"\n[Download] {len(failed)} FAILED:")
        for k, e in failed:
            print(f"  {k}: {e}")
        sys.exit(1)
    else:
        print(f"[Download] Done. Files written to {dest}/")


# ─────────────────────────────────────────────────────────────
# Public download (no credentials — R2 public bucket)
# ─────────────────────────────────────────────────────────────

def download_public(public_url: str, prefix: str, dest: Path, workers: int):
    """
    Download all objects under prefix from a public R2 bucket.
    Uses the bucket's public r2.dev URL — no credentials needed.

    Requires the bucket to have Public Access enabled in Cloudflare.
    """
    # First fetch the object listing via authenticated client to get keys,
    # then download each file via public HTTPS. If no creds are available,
    # we fall back to a manifest file approach.
    public_url = public_url.rstrip("/")

    # Try authenticated listing first (fastest)
    try:
        client = get_client()
        remote = list_remote_keys(client, _require("R2_BUCKET_NAME"), prefix)
        keys = list(remote.keys())
    except SystemExit:
        # No credentials — look for a manifest file at <prefix>/manifest.txt
        manifest_url = f"{public_url}/{prefix}/manifest.txt"
        resp = requests.get(manifest_url, timeout=30)
        if resp.status_code != 200:
            sys.exit(
                f"[ERROR] No credentials and no manifest found at {manifest_url}\n"
                f"        Run 'uv run r2-sync manifest' first (requires credentials)."
            )
        keys = [line.strip() for line in resp.text.splitlines() if line.strip()]

    print(f"[Download] {len(keys)} files via public URL: {public_url}")

    failed = []

    def _download_one(key: str):
        rel = key[len(prefix):].lstrip("/") if key.startswith(prefix) else key
        local = dest / rel
        if local.exists():
            return key, None   # skip already present
        local.parent.mkdir(parents=True, exist_ok=True)
        url = f"{public_url}/{key}"
        try:
            r = requests.get(url, stream=True, timeout=60)
            r.raise_for_status()
            with open(local, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 16):
                    f.write(chunk)
            return key, None
        except Exception as e:
            return key, str(e)

    with tqdm(total=len(keys), unit="file", desc="Downloading (public)") as bar:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_download_one, k): k for k in keys}
            for fut in as_completed(futures):
                key, err = fut.result()
                if err:
                    failed.append((key, err))
                bar.update(1)

    if failed:
        print(f"\n[Download] {len(failed)} FAILED:")
        for k, e in failed:
            print(f"  {k}: {e}")
        sys.exit(1)
    else:
        print(f"[Download] Done. Files written to {dest}/")


def write_manifest(bucket: str, prefix: str):
    """Write a manifest.txt listing all keys under prefix — needed for credential-free downloads."""
    client = get_client()
    remote = list_remote_keys(client, bucket, prefix)
    keys = sorted(remote.keys())

    manifest_key = f"{prefix}/manifest.txt"
    content = "\n".join(keys)
    client.put_object(
        Bucket=bucket,
        Key=manifest_key,
        Body=content.encode(),
        ContentType="text/plain",
    )
    print(f"[Manifest] {len(keys)} keys written to s3://{bucket}/{manifest_key}")


# ─────────────────────────────────────────────────────────────
# List
# ─────────────────────────────────────────────────────────────

def list_bucket(bucket: str, prefix: str):
    client = get_client()
    remote = list_remote_keys(client, bucket, prefix)
    if not remote:
        print(f"[List] No objects found under '{prefix}/'")
        return
    for key in sorted(remote):
        print(f"  {key}")
    print(f"\n[List] {len(remote)} objects in s3://{bucket}/{prefix}/")


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _content_type(path: Path) -> str:
    ext = path.suffix.lower()
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".json": "application/json",
        ".yaml": "application/yaml",
        ".yml": "application/yaml",
        ".txt": "text/plain",
        ".pt": "application/octet-stream",
    }.get(ext, "application/octet-stream")


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Sync ds/ dataset with Cloudflare R2")
    parser.add_argument(
        "--bucket", default=None,
        help="R2 bucket name (overrides R2_BUCKET_NAME in .env)"
    )
    parser.add_argument(
        "--prefix", default=None,
        help="Key prefix inside bucket (overrides R2_PREFIX in .env, default: 'ds')"
    )
    parser.add_argument(
        "--workers", type=int, default=16,
        help="Parallel upload/download threads (default: 16)"
    )

    sub = parser.add_subparsers(dest="cmd", required=True)

    up = sub.add_parser("upload", help="Upload ds/ to R2")
    up.add_argument(
        "--src", default="ds",
        help="Local directory to upload (default: ds/)"
    )
    up.add_argument(
        "--dry-run", action="store_true",
        help="Print what would be uploaded without doing it"
    )

    dl = sub.add_parser("download", help="Download dataset from R2")
    dl.add_argument(
        "--dest", default="ds",
        help="Local directory to download into (default: ds/)"
    )

    sub.add_parser("list", help="List objects in bucket under prefix")

    sub.add_parser(
        "manifest",
        help="Write manifest.txt to bucket (enables credential-free public downloads)"
    )

    args = parser.parse_args()

    bucket = args.bucket or _require("R2_BUCKET_NAME")
    prefix = (args.prefix or os.getenv("R2_PREFIX", "ds")).rstrip("/")

    if args.cmd == "upload":
        src = Path(args.src)
        if not src.exists():
            sys.exit(f"[ERROR] Source directory not found: {src}")
        upload(src, bucket, prefix, dry_run=args.dry_run, workers=args.workers)

    elif args.cmd == "download":
        public_url = os.getenv("R2_PUBLIC_URL", "").rstrip("/")
        if public_url:
            # Public bucket — no credentials needed
            download_public(public_url, prefix, dest=Path(args.dest), workers=args.workers)
        else:
            # Authenticated download
            download(bucket, prefix, dest=Path(args.dest), workers=args.workers)

    elif args.cmd == "list":
        list_bucket(bucket, prefix)

    elif args.cmd == "manifest":
        write_manifest(bucket, prefix)


if __name__ == "__main__":
    main()
