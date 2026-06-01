"""Idempotent pre-warm of the torch-free image models (YOLO ONNX + RapidOCR).

Loading the onnxruntime sessions takes a few seconds the first time; calling this
once (at server startup or before the first image in a scan) keeps it off the
per-file hot path. Safe to call repeatedly and from multiple threads.
"""

from __future__ import annotations

import os
import threading

_lock = threading.Lock()
_warmed = False


def _cap_threads() -> None:
    # Pin native math threads to 1. The scan runs files concurrently (see the
    # ThreadPool in scan_orchestrator), so parallelism comes from running many
    # files at once, not from each ONNX session fanning out. Capping at 1 keeps
    # total busy cores ≈ worker count, honouring the scan CPU budget instead of
    # letting workers × intra-op threads oversubscribe and freeze the machine.
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("ORT_NUM_THREADS", "1")


def warm_image_models() -> bool:
    """Load YOLO ONNX + RapidOCR once. Returns True when both are ready."""
    global _warmed
    with _lock:
        if _warmed:
            return True
        _cap_threads()
        from app.detectors.image import cascade, ocr, yolo

        yolo_ok = yolo.warm()
        ocr_ok = ocr.warm()
        cascade.warm()  # Haar refiners (bundled in opencv); best-effort
        _warmed = yolo_ok and ocr_ok
        return _warmed


def models_ready() -> bool:
    """True once a successful warm has completed."""
    return _warmed
