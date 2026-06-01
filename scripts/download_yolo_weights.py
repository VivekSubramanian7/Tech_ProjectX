"""Download default YOLO weights into data/models/ for local ML image scans."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = ROOT / "data" / "models"
DEFAULT_WEIGHTS = MODELS_DIR / "yolov8n.pt"


def main() -> int:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    if DEFAULT_WEIGHTS.is_file():
        print(f"weights already present: {DEFAULT_WEIGHTS}")
        return 0

    try:
        from ultralytics import YOLO
    except ImportError:
        print("Install ML deps first: pip install -e engine[ml]", file=sys.stderr)
        return 1

    print("Downloading yolov8n.pt via Ultralytics...")
    model = YOLO("yolov8n.pt")
    cwd_weights = Path("yolov8n.pt")
    if cwd_weights.is_file() and not DEFAULT_WEIGHTS.is_file():
        DEFAULT_WEIGHTS.write_bytes(cwd_weights.read_bytes())
    src = Path(getattr(model, "ckpt_path", "") or "")
    if src.is_file() and src.resolve() != DEFAULT_WEIGHTS.resolve():
        DEFAULT_WEIGHTS.write_bytes(src.read_bytes())
    elif not DEFAULT_WEIGHTS.is_file():
        # Ultralytics may have cached under user home; copy from predict cache if needed.
        import shutil

        cache_candidates = list(Path.home().glob("**/.cache/ultralytics/**/*.pt"))
        cache_candidates += list(Path.home().glob("**/yolov8n.pt"))
        for candidate in cache_candidates:
            if candidate.is_file() and candidate.stat().st_size > 1_000_000:
                shutil.copy2(candidate, DEFAULT_WEIGHTS)
                break

    if not DEFAULT_WEIGHTS.is_file():
        # Last resort: export current model weights to our path.
        model.save(str(DEFAULT_WEIGHTS))

    if DEFAULT_WEIGHTS.is_file():
        print(f"saved: {DEFAULT_WEIGHTS}")
        print(f"set: $env:GDPR_YOLO_WEIGHTS = \"{DEFAULT_WEIGHTS}\"")
        return 0

    print("failed to obtain yolov8n.pt", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
