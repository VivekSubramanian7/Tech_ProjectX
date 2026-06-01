"""Build-time: export YOLO11n to ONNX for torch-free runtime inference.

Run once during setup. Uses Ultralytics + torch (build-only). The serving process
loads the resulting ``data/models/yolo11n.onnx`` via onnxruntime and never imports
torch. Idempotent: skips if the .onnx already exists (pass --force to re-export).
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = ROOT / "data" / "models"
ONNX_OUT = MODELS_DIR / "yolo11n.onnx"
PT_NAME = "yolo11n.pt"
IMGSZ = 640
OPSET = 12


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="re-export even if ONNX exists")
    args = parser.parse_args()

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    if ONNX_OUT.is_file() and not args.force:
        print(f"ONNX already present: {ONNX_OUT}")
        return 0

    try:
        from ultralytics import YOLO
    except ImportError:
        print(
            "Ultralytics/torch are build-only deps. Install them to export: "
            "pip install ultralytics",
            file=sys.stderr,
        )
        return 1

    print(f"Loading {PT_NAME} (auto-downloads on first run via Ultralytics)…")
    model = YOLO(PT_NAME)

    print(f"Exporting to ONNX (imgsz={IMGSZ}, opset={OPSET}, dynamic=False)…")
    exported = model.export(format="onnx", imgsz=IMGSZ, opset=OPSET, dynamic=False)

    exported_path = Path(exported) if exported else None
    if exported_path is None or not exported_path.is_file():
        # Ultralytics writes <name>.onnx next to the .pt (often cwd).
        candidates = list(Path.cwd().glob("yolo11n.onnx"))
        candidates += list(Path.home().glob("**/yolo11n.onnx"))
        exported_path = next((c for c in candidates if c.is_file()), None)

    if exported_path is None or not exported_path.is_file():
        print("export failed: could not locate yolo11n.onnx", file=sys.stderr)
        return 1

    if exported_path.resolve() != ONNX_OUT.resolve():
        shutil.copy2(exported_path, ONNX_OUT)

    print(f"saved: {ONNX_OUT}  ({ONNX_OUT.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
