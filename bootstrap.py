"""
setup.py — Bootstrap truegrindapp on any machine (macOS, Linux, Windows)

Usage:
    python setup.py           # CPU / Apple MPS
    python setup.py --cuda    # NVIDIA GPU (CUDA 13.0)
"""

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENV_FILE = ROOT / ".env"
ENV_EXAMPLE = ROOT / ".env.example"


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    print(f"  $ {' '.join(cmd)}")
    return subprocess.run(cmd, check=check)


def find_uv() -> str | None:
    """Return the uv executable path, or None if not installed."""
    return shutil.which("uv")


def install_uv():
    """Install uv using the official installer (works on all platforms)."""
    system = platform.system()
    print("[setup] Installing uv...")

    if system == "Windows":
        run([
            "powershell", "-ExecutionPolicy", "ByPass", "-c",
            "irm https://astral.sh/uv/install.ps1 | iex",
        ])
    else:
        run(["sh", "-c", "curl -LsSf https://astral.sh/uv/install.sh | sh"])

    # Add common uv install locations to PATH for this session
    home = Path.home()
    extra_paths = [
        str(home / ".local" / "bin"),       # Linux / macOS
        str(home / ".cargo" / "bin"),        # cargo-style
        str(home / ".uv" / "bin"),           # Windows / newer uv
    ]
    os.environ["PATH"] = os.pathsep.join(extra_paths) + os.pathsep + os.environ["PATH"]

    if not find_uv():
        sys.exit(
            "[setup] uv installed but not found on PATH.\n"
            "        Close and reopen your terminal, then re-run: python setup.py"
        )


def sync_deps(cuda: bool):
    uv = find_uv()
    if cuda:
        print("[setup] Installing dependencies with CUDA 13.0...")
        run([uv, "sync", "--extra", "cuda"])
    else:
        print("[setup] Installing dependencies...")
        run([uv, "sync"])


def ensure_env():
    if ENV_FILE.exists():
        return True

    if not ENV_EXAMPLE.exists():
        sys.exit(f"[setup] {ENV_EXAMPLE} not found — is this the project root?")

    shutil.copy2(ENV_EXAMPLE, ENV_FILE)
    print()
    print("  .env created from .env.example.")
    print("  Fill in your credentials:")
    print()
    print("    ROBOFLOW_API_KEY  — app.roboflow.com -> Settings -> Roboflow API")
    print()
    print("  Then run:")
    print("    uv run grind train")
    print()
    return False


def main():
    cuda = "--cuda" in sys.argv

    os.chdir(ROOT)

    # 1. uv
    if not find_uv():
        install_uv()
    uv = find_uv()
    result = subprocess.run([uv, "--version"], capture_output=True, text=True)
    print(f"[setup] {result.stdout.strip()}")

    # 2. deps
    sync_deps(cuda)

    # 3. .env
    has_env = ensure_env()

    if has_env:
        print()
        print("  Ready. To train:")
        print("    uv run grind train")
        print("    uv run grind train --epochs 100 --weights yolov8s-seg.pt")
        print()
        print("  To run inference:")
        print("    uv run grind infer photo.jpg --model runs/segment/.../best.pt")
        print()


if __name__ == "__main__":
    main()
