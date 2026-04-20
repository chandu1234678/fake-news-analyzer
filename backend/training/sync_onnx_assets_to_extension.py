"""
Copy ONNX web export artifacts into extension model/runtime folders.

Usage:
  python backend/training/sync_onnx_assets_to_extension.py
"""

from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[2]
EXPORT_DIR = ROOT / "onnx_web"
EXT_MODELS_DIR = ROOT / "extension" / "models"
EXT_RUNTIME_DIR = ROOT / "extension" / "background" / "lib"

REQUIRED_MODEL_FILES = [
    "model_optimized.onnx",
    "tokenizer.json",
    "config.json",
]
OPTIONAL_MODEL_FILES = [
    "metadata.json",
]
RUNTIME_FILE = "ort.min.js"


def copy_if_exists(src: Path, dst: Path) -> bool:
    if not src.exists():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return True


def main() -> int:
    EXT_MODELS_DIR.mkdir(parents=True, exist_ok=True)
    EXT_RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

    if not EXPORT_DIR.exists():
        print(f"Export directory not found: {EXPORT_DIR}")
        print("Run backend/training/export_onnx_web.py first.")
        return 1

    copied = 0
    missing = []

    for filename in REQUIRED_MODEL_FILES:
        src = EXPORT_DIR / filename
        dst = EXT_MODELS_DIR / filename
        if copy_if_exists(src, dst):
            copied += 1
            print(f"Copied: {filename}")
        else:
            missing.append(filename)
            print(f"Missing: {filename}")

    for filename in OPTIONAL_MODEL_FILES:
        src = EXPORT_DIR / filename
        dst = EXT_MODELS_DIR / filename
        if copy_if_exists(src, dst):
            copied += 1
            print(f"Copied: {filename}")

    runtime_src = ROOT / "node_modules" / "onnxruntime-web" / "dist" / RUNTIME_FILE
    runtime_dst = EXT_RUNTIME_DIR / RUNTIME_FILE
    if copy_if_exists(runtime_src, runtime_dst):
        copied += 1
        print(f"Copied runtime: {RUNTIME_FILE}")
    else:
        print("Runtime not found in node_modules. Install onnxruntime-web and rerun if needed.")

    if missing:
        print("\nRequired files missing:")
        for item in missing:
            print(f"- {item}")
        return 2

    print(f"\nDone. Files copied: {copied}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
