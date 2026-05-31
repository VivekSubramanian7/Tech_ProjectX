"""OCR text-in-image → regex detectors (Story 3.4).

Uses EasyOCR when installed; falls back to PNG ``gdpr-ocr`` hints for fixtures.
"""

from __future__ import annotations

from pathlib import Path

from app.detectors.base import BBox, ImageDetection
from app.detectors.image._png import decode_image_once, read_png_text_chunks
from app.detectors.text.regex_checksum import RegexChecksumDetector

DETECTOR_VERSION = "ocr-0.2.0"
MODEL_VERSION = "easyocr-de-en"

_easyocr_reader = None


def _load_easyocr_reader():
    global _easyocr_reader
    if _easyocr_reader is not None:
        return _easyocr_reader
    try:
        import easyocr

        _easyocr_reader = easyocr.Reader(["de", "en"], gpu=False, verbose=False)
        return _easyocr_reader
    except Exception:
        return None


class OcrDetector:
    detector_version = DETECTOR_VERSION

    def __init__(self, *, min_pixels: int = 32 * 32, use_ml: bool = True) -> None:
        self.min_pixels = min_pixels
        self.use_ml = use_ml
        self._regex = RegexChecksumDetector()

    def detect(self, path: Path) -> list[ImageDetection]:
        try:
            decoded = decode_image_once(path)
        except ValueError:
            return []

        if decoded.width * decoded.height < self.min_pixels:
            return []

        if self.use_ml:
            ml = self._detect_easyocr(decoded)
            if ml:
                return ml

        return self._detect_hints(path)

    def _detect_easyocr(self, decoded) -> list[ImageDetection]:
        reader = _load_easyocr_reader()
        if reader is None:
            return []

        try:
            import numpy as np

            img = np.frombuffer(decoded.rgb, dtype=np.uint8).reshape(
                decoded.height, decoded.width, 3
            )
            results = reader.readtext(img)
        except Exception:
            return []

        findings: list[ImageDetection] = []
        for bbox_pts, text, conf in results:
            if not text.strip():
                continue
            xs = [p[0] for p in bbox_pts]
            ys = [p[1] for p in bbox_pts]
            norm = BBox(
                x=max(0.0, min(xs) / decoded.width),
                y=max(0.0, min(ys) / decoded.height),
                w=min(1.0, (max(xs) - min(xs)) / decoded.width),
                h=min(1.0, (max(ys) - min(ys)) / decoded.height),
            )
            for det in self._regex.detect(text, base_offset=0):
                findings.append(
                    ImageDetection(
                        classification_code=det.classification_code,
                        bbox=norm,
                        confidence_score=min(float(conf), det.confidence_score),
                        masked_snippet=det.masked_snippet,
                        detector_version=self.detector_version,
                        model_version=MODEL_VERSION,
                    )
                )
        return findings

    def _detect_hints(self, path: Path) -> list[ImageDetection]:
        chunks = read_png_text_chunks(path.read_bytes())
        text = chunks.get("gdpr-ocr", "")
        if not text:
            return []

        findings: list[ImageDetection] = []
        for det in self._regex.detect(text, base_offset=0):
            findings.append(
                ImageDetection(
                    classification_code=det.classification_code,
                    bbox=BBox(x=0.0, y=0.0, w=1.0, h=1.0),
                    confidence_score=det.confidence_score,
                    masked_snippet=det.masked_snippet,
                    detector_version=self.detector_version,
                    model_version=f"{MODEL_VERSION}-hint",
                )
            )
        return findings
