"""YOLO face/person & licence-plate detection (Story 3.3).

Uses Ultralytics when ``GDPR_YOLO_WEIGHTS`` points at a weights file; falls back
to embedded PNG ``gdpr-detect`` hints for deterministic fixtures / CI.
"""

from __future__ import annotations

import os
from pathlib import Path

from app.detectors.base import BBox, ImageDetection, mask_value
from app.detectors.image._png import read_png_text_chunks

DETECTOR_VERSION = "yolo-0.2.0"
MODEL_VERSION = "yolo26-weights"

# COCO class 0 = person; custom plate weights may add plate class via env label map.
_COCO_PERSON = 0

_yolo_model = None
_yolo_model_path: str | None = None


def _load_yolo_model():
    global _yolo_model, _yolo_model_path
    weights = os.environ.get("GDPR_YOLO_WEIGHTS", "")
    if not weights or not Path(weights).is_file():
        return None
    if _yolo_model is not None and _yolo_model_path == weights:
        return _yolo_model
    try:
        from ultralytics import YOLO

        _yolo_model = YOLO(weights)
        _yolo_model_path = weights
        return _yolo_model
    except Exception:
        return None


def _norm_bbox(x1: float, y1: float, x2: float, y2: float, w: int, h: int) -> BBox:
    if w <= 0 or h <= 0:
        return BBox(x=0.1, y=0.1, w=0.3, h=0.3)
    return BBox(
        x=max(0.0, x1 / w),
        y=max(0.0, y1 / h),
        w=min(1.0, (x2 - x1) / w),
        h=min(1.0, (y2 - y1) / h),
    )


def _map_class_name(name: str) -> str | None:
    key = name.lower().replace("-", "_")
    if key in {"person", "face"}:
        return "FACE"
    if key in {"license_plate", "licence_plate", "plate"}:
        return "LICENSE_PLATE"
    return None


class YoloDetector:
    detector_version = DETECTOR_VERSION

    def __init__(self, *, use_ml: bool = True) -> None:
        self.use_ml = use_ml

    def detect(self, path: Path) -> list[ImageDetection]:
        if self.use_ml:
            ml = self._detect_ultralytics(path)
            if ml:
                return ml
        return self._detect_hints(path)

    def _detect_ultralytics(self, path: Path) -> list[ImageDetection]:
        model = _load_yolo_model()
        if model is None:
            return []

        try:
            from app.detectors.image._png import decode_image_once

            decoded = decode_image_once(path)
        except ValueError:
            return []

        try:
            import numpy as np

            img = np.frombuffer(decoded.rgb, dtype=np.uint8).reshape(
                decoded.height, decoded.width, 3
            )
            results = model.predict(img, verbose=False, conf=0.25)
        except Exception:
            return []

        findings: list[ImageDetection] = []
        names = getattr(model, "names", {}) or {}
        for result in results:
            boxes = getattr(result, "boxes", None)
            if boxes is None:
                continue
            for box in boxes:
                cls_id = int(box.cls.item()) if hasattr(box.cls, "item") else int(box.cls)
                conf = float(box.conf.item()) if hasattr(box.conf, "item") else float(box.conf)
                label = names.get(cls_id, str(cls_id))
                code = _map_class_name(label)
                if code is None and cls_id == _COCO_PERSON:
                    code = "FACE"
                if code is None:
                    continue
                xyxy = box.xyxy[0].tolist()
                bbox = _norm_bbox(xyxy[0], xyxy[1], xyxy[2], xyxy[3], decoded.width, decoded.height)
                findings.append(
                    ImageDetection(
                        classification_code=code,
                        bbox=bbox,
                        confidence_score=conf,
                        masked_snippet=mask_value(code, visible_tail=2),
                        detector_version=self.detector_version,
                        model_version=MODEL_VERSION,
                    )
                )
        return findings

    def _detect_hints(self, path: Path) -> list[ImageDetection]:
        chunks = read_png_text_chunks(path.read_bytes())
        hint = chunks.get("gdpr-detect", "")
        if not hint:
            return []

        code, _, conf_str = hint.partition(":")
        try:
            conf = float(conf_str or "0.9")
        except ValueError:
            conf = 0.9

        if code not in {"FACE", "LICENSE_PLATE", "PERSON"}:
            return []

        bbox = BBox(x=0.1, y=0.1, w=0.3, h=0.3)
        return [
            ImageDetection(
                classification_code=code if code != "PERSON" else "FACE",
                bbox=bbox,
                confidence_score=conf,
                masked_snippet=mask_value(code, visible_tail=2),
                detector_version=self.detector_version,
                model_version=f"{MODEL_VERSION}-hint",
            )
        ]
