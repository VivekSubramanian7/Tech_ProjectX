"""Modality router tests (Story 3.1)."""

from pathlib import Path

from app.detectors.router import Modality, route_file, scannable_extensions


def test_txt_routes_to_text():
    assert route_file("notes.txt") == Modality.TEXT


def test_docx_is_scannable():
    assert ".docx" in scannable_extensions()


def test_docx_routes_to_text():
    assert route_file("report.docx") == Modality.TEXT


def test_png_routes_to_image():
    assert route_file("photo.png") == Modality.IMAGE


def test_jpeg_routes_to_image():
    assert route_file("scan.jpg") == Modality.IMAGE


def test_text_file_never_invokes_image_pipeline_marker(tmp_path):
    """Text files must not be classified as image modality."""
    p = tmp_path / "data.txt"
    p.write_text("hello", encoding="utf-8")
    assert route_file(str(p)) == Modality.TEXT


def test_scanned_pdf_routes_to_ocr(tmp_path):
    pdf = tmp_path / "scan.pdf"
    pdf.write_bytes(b"%PDF-1.4\n% scanned image-only\n")
    assert route_file(str(pdf), magic=b"%PDF-1.4\n% scanned image-only\n") == Modality.OCR


def test_native_text_pdf_routes_to_text(tmp_path):
    pdf = tmp_path / "native.pdf"
    pdf.write_bytes(b"%PDF-1.4\nBT /F1 12 Tf (Hello) Tj ET\n")
    assert route_file(str(pdf), magic=b"%PDF-1.4\nBT /F1 12 Tf (Hello) Tj ET\n") == Modality.TEXT
