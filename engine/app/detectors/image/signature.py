"""Signature detection in images (Story 3.5)."""

from __future__ import annotations

from pathlib import Path

from app.detectors.base import BBox, ImageDetection, mask_value
from app.detectors.image._png import read_png_text_chunks

DETECTOR_VERSION = "signature-stub-0.1.0"


class SignatureDetector:
    detector_version = DETECTOR_VERSION

    def __init__(self, *, enabled: bool = True) -> None:
        self.enabled = enabled

    def detect(self, path: Path) -> list[ImageDetection]:
        if not self.enabled:
            return []

        chunks = read_png_text_chunks(path.read_bytes())
        hint = chunks.get("gdpr-detect", "")
        if not hint.startswith("SIGNATURE"):
            return []

        _, _, conf_str = hint.partition(":")
        try:
            conf = float(conf_str or "0.85")
        except ValueError:
            conf = 0.85

        return [
            ImageDetection(
                classification_code="SIGNATURE",
                bbox=BBox(x=0.5, y=0.7, w=0.4, h=0.15),
                confidence_score=conf,
                masked_snippet=mask_value("signature", visible_tail=3),
                detector_version=self.detector_version,
                model_version=None,
            )
        ]
