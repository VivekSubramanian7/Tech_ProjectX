"""YOLO11 face/person detection via onnxruntime (torch-free runtime).

Runtime loads ``data/models/yolo11n.onnx`` (produced offline by
``scripts/export_models_onnx.py``) and infers with onnxruntime — no torch /
ultralytics import at serving time. Falls back to embedded PNG ``gdpr-detect``
hints when the ONNX model is absent (deterministic fixtures / CI).
"""

from __future__ import annotations

import os
from pathlib import Path

from app.detectors.base import BBox, ImageDetection, mask_value
from app.detectors.image._png import DecodedImage, decode_image_once, read_png_text_chunks

DETECTOR_VERSION = "yolo11-onnx-0.3.0"
MODEL_VERSION = "yolo11n-onnx"

_REPO_ROOT = Path(__file__).resolve().parents[4]
_DEFAULT_ONNX = _REPO_ROOT / "data" / "models" / "yolo11n.onnx"

# COCO coarse classes used as cascade stage-1 triggers.
_COCO_PERSON = 0
_COCO_VEHICLES = frozenset({2, 3, 5, 7})  # car, motorcycle, bus, truck
_INPUT_SIZE = 640
_CONF_THRES = 0.25
_IOU_THRES = 0.45

_session = None
_session_path: str | None = None


def _onnx_model_path() -> Path | None:
    override = os.environ.get("GDPR_YOLO_ONNX", "")
    candidate = Path(override) if override else _DEFAULT_ONNX
    return candidate if candidate.is_file() else None


def yolo_model_ready() -> bool:
    """Return True when the YOLO ONNX session can be loaded."""
    return _load_session() is not None


def _load_session():
    global _session, _session_path
    path = _onnx_model_path()
    if path is None:
        return None
    key = str(path)
    if _session is not None and _session_path == key:
        return _session
    try:
        import onnxruntime as ort

        # Single-threaded session: the scan parallelises across files, so each
        # session stays on one core to keep total CPU within the scan budget.
        so = ort.SessionOptions()
        so.intra_op_num_threads = 1
        so.inter_op_num_threads = 1
        _session = ort.InferenceSession(
            key, sess_options=so, providers=["CPUExecutionProvider"]
        )
        _session_path = key
        return _session
    except Exception:
        return None


def warm() -> bool:
    """Pre-load the ONNX session (used by startup / scan pre-warm)."""
    return _load_session() is not None


def _map_class_name(name: str) -> str | None:
    key = name.lower().replace("-", "_")
    if key in {"person", "face"}:
        return "FACE"
    if key in {"license_plate", "licence_plate", "plate"}:
        return "LICENSE_PLATE"
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


def _letterbox(decoded: DecodedImage):
    """Resize-with-pad decoded RGB to a 640x640 NCHW float tensor.

    Returns (tensor, gain, pad_x, pad_y) for undoing the transform.
    """
    import numpy as np
    from PIL import Image

    img = np.frombuffer(decoded.rgb, dtype=np.uint8).reshape(decoded.height, decoded.width, 3)
    h, w = decoded.height, decoded.width
    gain = min(_INPUT_SIZE / h, _INPUT_SIZE / w)
    new_w, new_h = max(1, round(w * gain)), max(1, round(h * gain))
    pad_x = (_INPUT_SIZE - new_w) / 2
    pad_y = (_INPUT_SIZE - new_h) / 2

    resized = Image.fromarray(img).resize((new_w, new_h), Image.BILINEAR)
    canvas = np.full((_INPUT_SIZE, _INPUT_SIZE, 3), 114, dtype=np.uint8)
    top, left = int(round(pad_y - 0.1)), int(round(pad_x - 0.1))
    canvas[top : top + new_h, left : left + new_w] = np.asarray(resized)

    tensor = canvas.astype(np.float32) / 255.0
    tensor = tensor.transpose(2, 0, 1)[None]  # NCHW
    return np.ascontiguousarray(tensor), gain, left, top


def _nms(boxes, scores, iou_thres: float):
    """Pure-numpy non-max suppression. boxes = [N,4] x1y1x2y2."""
    import numpy as np

    if len(boxes) == 0:
        return []
    x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
    areas = (x2 - x1).clip(min=0) * (y2 - y1).clip(min=0)
    order = scores.argsort()[::-1]
    keep: list[int] = []
    while order.size > 0:
        i = int(order[0])
        keep.append(i)
        if order.size == 1:
            break
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        inter = (xx2 - xx1).clip(min=0) * (yy2 - yy1).clip(min=0)
        iou = inter / (areas[i] + areas[order[1:]] - inter + 1e-9)
        order = order[1:][iou <= iou_thres]
    return keep


class YoloDetector:
    detector_version = DETECTOR_VERSION

    def __init__(self, *, use_ml: bool = True) -> None:
        self.use_ml = use_ml

    def detect(
        self,
        path: Path,
        *,
        decoded: DecodedImage | None = None,
        data: bytes | None = None,
    ) -> list[ImageDetection]:
        if self.use_ml:
            ml = self._detect_onnx(path, decoded)
            if ml:
                return ml
        return self._detect_hints(path, data)

    def _detect_onnx(self, path: Path, decoded: DecodedImage | None) -> list[ImageDetection]:
        session = _load_session()
        if session is None:
            return []
        try:
            import numpy as np

            if decoded is None:
                decoded = decode_image_once(path)
            tensor, gain, pad_x, pad_y = _letterbox(decoded)
            input_name = session.get_inputs()[0].name
            outputs = session.run(None, {input_name: tensor})
        except Exception:
            return []

        preds = outputs[0]
        if preds.ndim == 3:
            preds = preds[0]
        preds = preds.T  # [num_anchors, 84]
        boxes_cxcywh = preds[:, :4]
        class_scores = preds[:, 4:]
        class_ids = class_scores.argmax(axis=1)
        confs = class_scores.max(axis=1)

        keep_mask = confs >= _CONF_THRES
        if not keep_mask.any():
            return []
        boxes_cxcywh = boxes_cxcywh[keep_mask]
        class_ids = class_ids[keep_mask]
        confs = confs[keep_mask]

        # cxcywh (letterboxed 640 space) → xyxy in original-image pixels
        cx, cy, bw, bh = (
            boxes_cxcywh[:, 0],
            boxes_cxcywh[:, 1],
            boxes_cxcywh[:, 2],
            boxes_cxcywh[:, 3],
        )
        x1 = (cx - bw / 2 - pad_x) / gain
        y1 = (cy - bh / 2 - pad_y) / gain
        x2 = (cx + bw / 2 - pad_x) / gain
        y2 = (cy + bh / 2 - pad_y) / gain
        xyxy = np.stack([x1, y1, x2, y2], axis=1)

        keep = _nms(xyxy, confs, _IOU_THRES)

        # Full-image RGB array for the stage-2 Haar cascade crops.
        rgb = np.frombuffer(decoded.rgb, dtype=np.uint8).reshape(
            decoded.height, decoded.width, 3
        )

        findings: list[ImageDetection] = []
        for i in keep:
            cls_id = int(class_ids[i])
            conf = float(confs[i])
            box = (
                int(xyxy[i, 0]),
                int(xyxy[i, 1]),
                int(xyxy[i, 2]),
                int(xyxy[i, 3]),
            )
            if cls_id == _COCO_PERSON:
                findings.extend(self._refine_person(rgb, box, conf, decoded))
            elif cls_id in _COCO_VEHICLES:
                findings.extend(self._refine_vehicle(rgb, box, conf, decoded))
        return findings

    def _emit(self, code, px_box, conf, decoded) -> ImageDetection:
        bbox = _norm_bbox(
            float(px_box[0]), float(px_box[1]), float(px_box[2]), float(px_box[3]),
            decoded.width, decoded.height,
        )
        return ImageDetection(
            classification_code=code,
            bbox=bbox,
            confidence_score=round(float(conf), 4),
            masked_snippet=mask_value(code, visible_tail=2),
            detector_version=self.detector_version,
            model_version=MODEL_VERSION,
        )

    def _refine_person(self, rgb, person_box, conf, decoded) -> list[ImageDetection]:
        """Stage-2: a person region only matters for GDPR if it contains a face.

        A bare arm/leg/torso is not identifying personal data, so we emit a FACE
        finding only when the Haar face cascade confirms an actual face; otherwise
        nothing is surfaced to the owner.
        """
        from app.detectors.image import cascade

        faces = cascade.detect_faces(rgb, person_box)
        if not faces:
            return []
        # Two detectors agree (YOLO person + Haar face) → confident biometric.
        face_conf = min(0.98, conf + 0.2)
        return [self._emit("FACE", fb, face_conf, decoded) for fb in faces]

    def _refine_vehicle(self, rgb, vehicle_box, conf, decoded) -> list[ImageDetection]:
        """Stage-2: vehicle → LICENSE_PLATE only if a plate region is found inside."""
        from app.detectors.image import cascade

        plates = cascade.detect_plates(rgb, vehicle_box)
        plate_conf = min(0.95, conf + 0.1)
        return [self._emit("LICENSE_PLATE", pb, plate_conf, decoded) for pb in plates]

    def _detect_hints(self, path: Path, data: bytes | None) -> list[ImageDetection]:
        raw = data if data is not None else path.read_bytes()
        chunks = read_png_text_chunks(raw)
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
