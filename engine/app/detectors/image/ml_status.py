"""Report ML image detector availability (YOLO ONNX session, RapidOCR).

Torch-free: probes the onnxruntime-based runtime stack without importing
torch / ultralytics / easyocr.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MlImageStatus:
    use_ml_image: bool
    yolo_onnx_path: str | None
    yolo_ready: bool
    ocr_ready: bool

    def summary(self) -> str:
        if not self.use_ml_image:
            return "image ML disabled (use_ml_image=false); PNG gdpr-* hints only"
        parts = [
            f"yolo={'ready' if self.yolo_ready else 'unavailable'}",
            f"ocr={'ready' if self.ocr_ready else 'unavailable'}",
        ]
        if self.yolo_onnx_path:
            parts.append(f"onnx={self.yolo_onnx_path}")
        elif not self.yolo_ready:
            parts.append("onnx=unset (run scripts/export_models_onnx.py)")
        if not self.ocr_ready:
            parts.append("rapidocr=not installed")
        return "image ML: " + ", ".join(parts)


def probe_ml_image_status(*, use_ml_image: bool = True) -> MlImageStatus:
    from app.detectors.image import yolo
    from app.detectors.image.ocr import rapidocr_installed

    onnx_path = yolo._onnx_model_path()
    yolo_ready = False
    ocr_ready = False
    if use_ml_image:
        yolo_ready = yolo.yolo_model_ready()
        ocr_ready = rapidocr_installed()

    return MlImageStatus(
        use_ml_image=use_ml_image,
        yolo_onnx_path=str(onnx_path) if onnx_path else None,
        yolo_ready=yolo_ready,
        ocr_ready=ocr_ready,
    )
