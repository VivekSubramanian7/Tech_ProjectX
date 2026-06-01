"""Stage-2 cascade refiners using OpenCV Haar cascades (bundled in opencv-python).

Zero extra model files / no torch: the coarse YOLO11 ONNX detects ``person`` /
vehicle regions, and these deterministic Haar classifiers refine them into a
``FACE`` (actual face) or ``LICENSE_PLATE``. Fixed parameters keep results
reproducible. All boxes are returned in full-image pixel coordinates.
"""

from __future__ import annotations

from functools import lru_cache

# Tuned for precision over recall on the refined crop (the coarse stage already
# provides recall). Deterministic — no randomness.
_FACE_SCALE = 1.1
_FACE_MIN_NEIGHBORS = 5
_PLATE_SCALE = 1.1
_PLATE_MIN_NEIGHBORS = 4


@lru_cache(maxsize=1)
def _face_cascade():
    import cv2

    path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    clf = cv2.CascadeClassifier(path)
    return clf if not clf.empty() else None


@lru_cache(maxsize=1)
def _plate_cascade():
    import cv2

    path = cv2.data.haarcascades + "haarcascade_russian_plate_number.xml"
    clf = cv2.CascadeClassifier(path)
    return clf if not clf.empty() else None


def warm() -> bool:
    """Pre-load both cascades (cheap; keeps them off the per-file hot path)."""
    return _face_cascade() is not None and _plate_cascade() is not None


def _gray_crop(rgb, box: tuple[int, int, int, int]):
    import cv2
    import numpy as np

    h, w = rgb.shape[:2]
    x1, y1, x2, y2 = box
    x1 = max(0, min(int(x1), w - 1))
    y1 = max(0, min(int(y1), h - 1))
    x2 = max(x1 + 1, min(int(x2), w))
    y2 = max(y1 + 1, min(int(y2), h))
    crop = rgb[y1:y2, x1:x2]
    if crop.size == 0:
        return None, (x1, y1)
    gray = cv2.cvtColor(np.ascontiguousarray(crop), cv2.COLOR_RGB2GRAY)
    return gray, (x1, y1)


def _detect(cascade, rgb, box, scale: float, min_neighbors: int) -> list[tuple[int, int, int, int]]:
    if cascade is None:
        return []
    gray, (ox, oy) = _gray_crop(rgb, box)
    if gray is None:
        return []
    try:
        rects = cascade.detectMultiScale(gray, scaleFactor=scale, minNeighbors=min_neighbors)
    except Exception:
        return []
    out: list[tuple[int, int, int, int]] = []
    for (x, y, w, h) in rects:
        out.append((ox + int(x), oy + int(y), ox + int(x) + int(w), oy + int(y) + int(h)))
    return out


def detect_faces(rgb, box: tuple[int, int, int, int]) -> list[tuple[int, int, int, int]]:
    """Find faces inside a person region. Boxes are full-image pixel coords."""
    return _detect(_face_cascade(), rgb, box, _FACE_SCALE, _FACE_MIN_NEIGHBORS)


def detect_plates(rgb, box: tuple[int, int, int, int]) -> list[tuple[int, int, int, int]]:
    """Find licence-plate regions inside a vehicle region. Full-image pixel coords."""
    return _detect(_plate_cascade(), rgb, box, _PLATE_SCALE, _PLATE_MIN_NEIGHBORS)
