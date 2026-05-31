"""Image pipeline + detector tests (Stories 3.2–3.5)."""

import struct
import zlib
from pathlib import Path

import pytest

from app.detectors.image.ocr import OcrDetector
from app.detectors.image.pipeline import ImagePipeline, decode_image_once
from app.detectors.image.signature import SignatureDetector
from app.detectors.image.yolo import YoloDetector


def _png_with_text_chunks(chunks: dict[str, str], width: int = 64, height: int = 64) -> bytes:
    """Build a minimal RGB PNG with optional tEXt metadata chunks."""
    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    raw = b""
    row = b"\x00" + (b"\xff\x00\x00" * width)
    for _ in range(height):
        raw += row
    idat = zlib.compress(raw)

    parts = [b"\x89PNG\r\n\x1a\n", chunk(b"IHDR", ihdr), chunk(b"IDAT", idat)]
    for key, val in chunks.items():
        text = (key + "\0" + val).encode("latin-1")
        parts.append(chunk(b"tEXt", text))
    parts.append(chunk(b"IEND", b""))
    return b"".join(parts)


@pytest.fixture
def face_png(tmp_path: Path) -> Path:
    p = tmp_path / "face.png"
    p.write_bytes(_png_with_text_chunks({"gdpr-detect": "FACE:0.93"}))
    return p


@pytest.fixture
def plate_png(tmp_path: Path) -> Path:
    p = tmp_path / "plate.png"
    p.write_bytes(_png_with_text_chunks({"gdpr-detect": "LICENSE_PLATE:0.88"}))
    return p


@pytest.fixture
def signature_png(tmp_path: Path) -> Path:
    p = tmp_path / "sig.png"
    p.write_bytes(_png_with_text_chunks({"gdpr-detect": "SIGNATURE:0.85"}))
    return p


@pytest.fixture
def passport_ocr_png(tmp_path: Path) -> Path:
    p = tmp_path / "passport.png"
    p.write_bytes(
        _png_with_text_chunks(
            {
                "gdpr-ocr": "Passport No: X12345678",
            }
        )
    )
    return p


def test_decode_image_once_shared_array(face_png: Path):
    arr1 = decode_image_once(face_png)
    arr2 = decode_image_once(face_png)
    assert arr1.shape == arr2.shape
    assert arr1.tobytes() == arr2.tobytes()


def test_pipeline_batches_images(face_png: Path, plate_png: Path):
    pipe = ImagePipeline(batch_size=2)
    results = pipe.run([face_png, plate_png])
    assert len(results) == 2
    assert all(r.decoded is not None for r in results)


def test_yolo_detects_face(face_png: Path):
    det = YoloDetector()
    findings = det.detect(face_png)
    assert any(f.classification_code == "FACE" for f in findings)


def test_yolo_detects_license_plate(plate_png: Path):
    det = YoloDetector()
    findings = det.detect(plate_png)
    assert any(f.classification_code == "LICENSE_PLATE" for f in findings)


def test_yolo_is_deterministic(face_png: Path):
    det = YoloDetector()
    a = det.detect(face_png)
    b = det.detect(face_png)
    assert [(f.classification_code, f.bbox) for f in a] == [
        (f.classification_code, f.bbox) for f in b
    ]


def test_ocr_feeds_passport_text_detector(passport_ocr_png: Path):
    det = OcrDetector()
    findings = det.detect(passport_ocr_png)
    assert any(f.classification_code == "PASSPORT_NUMBER" for f in findings)


def test_ocr_skips_tiny_images(tmp_path: Path):
    tiny = tmp_path / "icon.png"
    tiny.write_bytes(_png_with_text_chunks({"gdpr-ocr": "ignored"}, width=8, height=8))
    det = OcrDetector(min_pixels=32 * 32)
    assert det.detect(tiny) == []


def test_signature_detector_toggleable(signature_png: Path):
    enabled = SignatureDetector(enabled=True)
    disabled = SignatureDetector(enabled=False)
    assert enabled.detect(signature_png)
    assert disabled.detect(signature_png) == []
