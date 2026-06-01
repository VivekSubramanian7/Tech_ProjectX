"""Verify ML image scan produces non-hint YOLO findings on a real JPEG."""

from __future__ import annotations

import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))

WEIGHTS = ROOT / "data" / "models" / "yolov8n.pt"
SAMPLE_URL = "https://ultralytics.com/images/bus.jpg"
SAMPLE_DIR = ROOT / "data" / "ml_image_test"
SAMPLE_JPG = SAMPLE_DIR / "bus.jpg"


def main() -> int:
    if not WEIGHTS.is_file():
        print(f"missing weights: {WEIGHTS}", file=sys.stderr)
        return 1

    os.environ["GDPR_YOLO_WEIGHTS"] = str(WEIGHTS)
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    if not SAMPLE_JPG.is_file():
        print(f"downloading sample image: {SAMPLE_URL}")
        urllib.request.urlretrieve(SAMPLE_URL, SAMPLE_JPG)

    from app.detectors.image.ml_status import probe_ml_image_status
    from app.detectors.image.yolo import YoloDetector
    from app.repositories import CatalogRepository
    from app.scan_config import ScanOptions
    from app.services.scan_orchestrator import ScanOrchestrator

    status = probe_ml_image_status(use_ml_image=True)
    print(status.summary())
    if not status.yolo_ready:
        print("YOLO not ready", file=sys.stderr)
        return 1

    det = YoloDetector(use_ml=True)
    findings = det.detect(SAMPLE_JPG)
    face = [f for f in findings if f.classification_code == "FACE"]
    if not face:
        print("no FACE detections on bus.jpg", file=sys.stderr)
        return 1
    if face[0].model_version and face[0].model_version.endswith("-hint"):
        print("detector fell back to PNG hints", file=sys.stderr)
        return 1
    print(f"YOLO ML finding: model_version={face[0].model_version}, bbox={face[0].bbox}")

    db = ROOT / "data" / ".ml_verify_catalog.sqlite"
    if db.is_file():
        db.unlink()
    repo = CatalogRepository(db)
    seed = ROOT / "data" / "enum_seed.sql"
    repo.init_db(seed if seed.is_file() else None)
    orch = ScanOrchestrator(repo, ownership_map_path=ROOT / "data" / "mock_owners.json")
    result = orch.run_scan(SAMPLE_DIR, mode="full", options=ScanOptions(use_ml_image=True))
    scan_faces = [f for f in result["findings"] if f.get("code") == "FACE" and f.get("modality") == "image"]
    if not scan_faces:
        print("orchestrator scan produced no image FACE findings", file=sys.stderr)
        return 1

    print(f"scan OK: {len(scan_faces)} FACE finding(s), files_scanned={result['files_scanned']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
