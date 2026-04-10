"""
roboflow_prep.py — Download public grain/particle datasets and merge into one
==============================================================================

Downloads Roboflow datasets, remaps all class labels → 'particle',
then merges into a single YOLOv8-Segmentation dataset ready for training.

Output layout:
    data/
      images/train/   images/val/
      labels/train/   labels/val/
      data.yaml

Usage:
    uv run prep-data

Then train:
    uv run grind train data/data.yaml --epochs 50

Requires ROBOFLOW_API_KEY in .env
"""

import os
import sys
import shutil
import random
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("ROBOFLOW_API_KEY")

# ─────────────────────────────────────────────────────────────
# Datasets to download
# ─────────────────────────────────────────────────────────────

DATASETS = [
    # (workspace, project, version, format)
    # Grain polygon masks — rice/corn/wheat (verified, 190+ images)
    ("winxos-16ly4",           "grain-3z0bc",                    11, "yolov8"),
    # Particle segmentation v2 — small granular particles (50 images)
    ("particle-training",      "particle-segmentation-v2-wxihe", 12, "yolov8"),
    # Seed instance segmentation — seeds on a plain surface (245 images)
    ("seed-mrn2d",             "seed-instance-segmentation",      5, "yolov8"),
    # Coffee bean segmentation — individual coffee beans (145 images)
    ("kopi-otjpe",             "coffee-bean-ztxe3",               2, "yolov8"),
    # Rice grain segmentation — dense small grains (104 images)
    ("sagmentrice",            "rice-grain-segmentation-jcaab",   8, "yolov8"),
]

RAW_DIR  = Path("raw_datasets")    # where Roboflow downloads land
OUT_DIR  = Path("data")            # final merged dataset
YAML_OUT = OUT_DIR / "data.yaml"

VAL_SPLIT = 0.15   # 15% of merged data goes to val


# ─────────────────────────────────────────────────────────────
# Step 1: Download
# ─────────────────────────────────────────────────────────────

def download_all() -> list[Path]:
    from roboflow import Roboflow
    rf = Roboflow(api_key=API_KEY)
    roots = []

    RAW_DIR.mkdir(exist_ok=True)

    for workspace, project_name, version, fmt in DATASETS:
        dest = RAW_DIR / project_name
        if dest.exists():
            print(f"[Download] {project_name} already downloaded, skipping.")
            roots.append(dest)
            continue

        print(f"[Download] {workspace}/{project_name} v{version} …")
        try:
            project = rf.workspace(workspace).project(project_name)
            dataset = project.version(version).download(fmt, location=str(dest))
            roots.append(dest)
            print(f"[Download] Saved to {dest}")
        except Exception as e:
            print(f"[WARNING] Skipping {project_name}: {e}")

    return roots


# ─────────────────────────────────────────────────────────────
# Step 2: Remap labels → all classes become class 0 'particle'
# ─────────────────────────────────────────────────────────────

def remap_label_file(src: Path, dst: Path):
    """
    YOLOv8 label format: <class_id> <x1> <y1> ... per line
    Replace whatever class_id is with 0 (particle).
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    lines = src.read_text().strip().splitlines()
    remapped = []
    for line in lines:
        if not line.strip():
            continue
        parts = line.split()
        parts[0] = "0"          # remap to particle
        remapped.append(" ".join(parts))
    dst.write_text("\n".join(remapped) + "\n" if remapped else "")


# ─────────────────────────────────────────────────────────────
# Step 3: Collect all (image, label) pairs from a downloaded root
# ─────────────────────────────────────────────────────────────

def collect_pairs(root: Path) -> list[tuple[Path, Path | None]]:
    """
    Roboflow exports can have train/valid/test splits or a flat layout.
    We flatten everything into one pool and re-split ourselves.
    Returns list of (image_path, label_path_or_None).
    """
    pairs = []
    img_exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

    for split in ["train", "valid", "test", ""]:
        img_dir = root / split / "images" if split else root / "images"
        lbl_dir = root / split / "labels" if split else root / "labels"

        if not img_dir.exists():
            continue

        for img in sorted(img_dir.iterdir()):
            if img.suffix.lower() not in img_exts:
                continue
            lbl = lbl_dir / (img.stem + ".txt")
            pairs.append((img, lbl if lbl.exists() else None))

    return pairs


# ─────────────────────────────────────────────────────────────
# Step 4: Merge & write final dataset
# ─────────────────────────────────────────────────────────────

def build_merged(roots: list[Path]):
    all_pairs: list[tuple[Path, Path | None]] = []
    for root in roots:
        pairs = collect_pairs(root)
        print(f"[Merge] {root.name}: {len(pairs)} images")
        all_pairs.extend(pairs)

    print(f"[Merge] Total: {len(all_pairs)} images across all datasets")

    random.seed(42)
    random.shuffle(all_pairs)

    n_val   = max(1, int(len(all_pairs) * VAL_SPLIT))
    val_set  = all_pairs[:n_val]
    train_set = all_pairs[n_val:]

    print(f"[Merge] train={len(train_set)}  val={len(val_set)}")

    for split_name, split_pairs in [("train", train_set), ("val", val_set)]:
        img_out = OUT_DIR / "images" / split_name
        lbl_out = OUT_DIR / "labels" / split_name
        img_out.mkdir(parents=True, exist_ok=True)
        lbl_out.mkdir(parents=True, exist_ok=True)

        for i, (img_path, lbl_path) in enumerate(split_pairs):
            # Unique filename: dataset_name + original stem to avoid collisions
            stem = f"{img_path.parent.parent.parent.name}__{img_path.stem}"
            shutil.copy2(img_path, img_out / (stem + img_path.suffix))

            dst_lbl = lbl_out / (stem + ".txt")
            if lbl_path:
                remap_label_file(lbl_path, dst_lbl)
            else:
                dst_lbl.write_text("")   # empty label = background image

    # Write data.yaml
    yaml_content = (
        f"path: {OUT_DIR.resolve()}\n"
        f"train: images/train\n"
        f"val: images/val\n"
        f"nc: 1\n"
        f"names: ['particle']\n"
    )
    YAML_OUT.write_text(yaml_content)
    print(f"[Merge] data.yaml written to {YAML_OUT}")
    print(f"\n[Done] Dataset ready at {OUT_DIR}/")
    print(f"       Train with:  uv run grind train {YAML_OUT} --epochs 50")


# ─────────────────────────────────────────────────────────────
# Entrypoint
# ─────────────────────────────────────────────────────────────

def main():
    if not API_KEY:
        sys.exit(
            "[ERROR] Missing ROBOFLOW_API_KEY in .env\n"
            "        Get yours at app.roboflow.com → Settings → Roboflow API"
        )

    if OUT_DIR.exists():
        print(f"[Info] {OUT_DIR}/ already exists. Delete it to rebuild from scratch.")

    roots = download_all()
    build_merged(roots)


if __name__ == "__main__":
    main()
