"""OCR text-in-image → regex detectors via RapidOCR (torch-free runtime).

Uses RapidOCR (onnxruntime, bundled ONNX det+rec models) — no torch / easyocr
import at serving time. Falls back to PNG ``gdpr-ocr`` hints for fixtures / CI.
"""

from __future__ import annotations

from pathlib import Path

from app.detectors.base import BBox, ImageDetection
from app.detectors.image._png import DecodedImage, decode_image_once, read_png_text_chunks
from app.detectors.text.regex_checksum import RegexChecksumDetector

DETECTOR_VERSION = "ocr-rapidocr-0.3.0"
MODEL_VERSION = "rapidocr-onnx"

# Cap the longest edge fed to OCR — CPU inference cost scales with pixel count.
_MAX_OCR_EDGE = 1280

_rapidocr = None


def rapidocr_installed() -> bool:
    """Return True when the rapidocr_onnxruntime package is importable."""
    try:
        import rapidocr_onnxruntime  # noqa: F401

        return True
    except ImportError:
        return False


def ocr_reader_ready() -> bool:
    """Return True when the RapidOCR engine initialized successfully."""
    return _load_rapidocr() is not None


def warm() -> bool:
    """Pre-load the RapidOCR engine (used by startup / scan pre-warm)."""
    return _load_rapidocr() is not None


def _load_rapidocr():
    global _rapidocr
    if _rapidocr is not None:
        return _rapidocr
    try:
        from rapidocr_onnxruntime import RapidOCR

        _rapidocr = RapidOCR()
        return _rapidocr
    except Exception:
        return None


def _downscale(decoded: DecodedImage):
    """Return an HxWx3 uint8 RGB numpy array, longest edge ≤ _MAX_OCR_EDGE."""
    import numpy as np

    img = np.frombuffer(decoded.rgb, dtype=np.uint8).reshape(decoded.height, decoded.width, 3)
    longest = max(decoded.width, decoded.height)
    if longest <= _MAX_OCR_EDGE:
        return img
    from PIL import Image

    scale = _MAX_OCR_EDGE / longest
    new_w = max(1, round(decoded.width * scale))
    new_h = max(1, round(decoded.height * scale))
    resized = Image.fromarray(img).resize((new_w, new_h), Image.BILINEAR)
    return np.asarray(resized)


class OcrDetector:
    detector_version = DETECTOR_VERSION

    def __init__(self, *, min_pixels: int = 32 * 32, use_ml: bool = True) -> None:
        self.min_pixels = min_pixels
        self.use_ml = use_ml
        self._regex = RegexChecksumDetector()

    def detect(
        self,
        path: Path,
        *,
        decoded: DecodedImage | None = None,
        data: bytes | None = None,
    ) -> list[ImageDetection]:
        if decoded is None:
            try:
                decoded = decode_image_once(path)
            except ValueError:
                return []

        if decoded.width * decoded.height < self.min_pixels:
            return []

        if self.use_ml:
            ml = self._detect_rapidocr(decoded)
            if ml:
                return ml

        return self._detect_hints(path, data)

    def _detect_rapidocr(self, decoded: DecodedImage) -> list[ImageDetection]:
        engine = _load_rapidocr()
        if engine is None:
            return []

        try:
            img = _downscale(decoded)
            result, _elapsed = engine(img)
        except Exception:
            return []

        if not result:
            return []

        findings: list[ImageDetection] = []
        for box_pts, text, conf in result:
            if not text or not text.strip():
                continue
            xs = [p[0] for p in box_pts]
            ys = [p[1] for p in box_pts]
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

    def _detect_hints(self, path: Path, data: bytes | None) -> list[ImageDetection]:
        raw = data if data is not None else path.read_bytes()
        chunks = read_png_text_chunks(raw)
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
