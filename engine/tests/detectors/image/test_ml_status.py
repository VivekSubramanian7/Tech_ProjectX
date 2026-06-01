"""Tests for ML image availability probe (torch-free ONNX stack)."""

from app.detectors.image.ml_status import probe_ml_image_status


def test_probe_when_ml_disabled():
    status = probe_ml_image_status(use_ml_image=False)
    assert status.use_ml_image is False
    assert "disabled" in status.summary()


def test_probe_yolo_unavailable_when_onnx_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("GDPR_YOLO_ONNX", str(tmp_path / "missing.onnx"))
    status = probe_ml_image_status(use_ml_image=True)
    assert status.yolo_ready is False
    assert status.yolo_onnx_path is None
    assert "unset" in status.summary() or "unavailable" in status.summary()


def test_probe_ocr_ready_reports_rapidocr(monkeypatch):
    status = probe_ml_image_status(use_ml_image=True)
    # rapidocr-onnxruntime is a runtime dependency; it should be importable.
    assert status.ocr_ready is True
