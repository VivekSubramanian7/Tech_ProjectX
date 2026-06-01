"""Text extraction tests."""

import io
from pathlib import Path

from app.detectors.text.extract import extract_docx_bytes, extract_file, extract_plain_text, extract_pptx_bytes, segments_from_text
from app.detectors.text.regex_checksum import RegexChecksumDetector

from office_fixtures import minimal_docx, minimal_pptx

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


def test_extract_docx_bytes():
    data = minimal_docx("Contact: test@example.com")
    text = extract_docx_bytes(data)
    assert "test@example.com" in text


def test_extract_file_docx(tmp_path: Path):
    path = tmp_path / "note.docx"
    path.write_bytes(minimal_docx("Email: user@corp.de"))
    with path.open("rb") as f:
        segments, content_hash = extract_file(str(path), f)
    joined = "".join(s.text for s in segments)
    assert "user@corp.de" in joined
    assert len(content_hash) == 64


def test_extract_pptx_bytes():
    data = minimal_pptx(["Quarterly revenue", "Contact: slide@example.com"])
    text = extract_pptx_bytes(data)
    assert "--- Slide 1 ---" in text
    assert "Quarterly revenue" in text
    assert "slide@example.com" in text


def test_extract_file_pptx(tmp_path: Path):
    path = tmp_path / "deck.pptx"
    path.write_bytes(minimal_pptx(["Email: deck@corp.de"]))
    with path.open("rb") as f:
        segments, content_hash = extract_file(str(path), f)
    joined = "".join(s.text for s in segments)
    assert "deck@corp.de" in joined
    assert len(content_hash) == 64


class _NonSeekableReader:
    """Mimics a source reader (e.g. ChunkedReader) that pypdf can't seek."""

    def __init__(self, data: bytes) -> None:
        self._data = data

    def readall(self) -> bytes:
        return self._data

    def read(self, size: int = -1) -> bytes:
        return self._data


def test_extract_file_pdf_from_non_seekable_stream():
    """PDF extraction must work even when the source stream has no seek()."""
    import pytest

    reportlab = pytest.importorskip("reportlab")
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(72, 720, "Email: pdf_user@corp.de")
    c.showPage()
    c.save()

    segments, content_hash = extract_file("doc.pdf", _NonSeekableReader(buf.getvalue()))
    joined = "".join(s.text for s in segments)
    assert "pdf_user@corp.de" in joined
    assert len(content_hash) == 64


def test_segments_have_global_offsets():
    text = "line1\nline2\nline3\n"
    segs = list(segments_from_text(text, chunk_chars=8, overlap=2))
    assert segs[0].base_offset == 0
    assert "".join(s.text for s in segs) != "" or text == ""


def test_content_hash_matches_full_file():
    path = FIXTURES / "tiny.txt"
    with path.open("rb") as f:
        _, h1 = extract_plain_text(f, ".txt")
    with path.open("rb") as f:
        import hashlib

        h2 = hashlib.sha256(f.read()).hexdigest()
    assert h1 == h2


def test_boundary_email_detected_once_with_overlap():
    text = (FIXTURES / "boundary_span.txt").read_text(encoding="utf-8")
    regex = RegexChecksumDetector()
    triples = []
    for seg in segments_from_text(text, chunk_chars=200, overlap=32):
        for det in regex.detect(seg.text, seg.base_offset):
            triples.append((det.span.start, det.span.end, det.classification_code))
    emails = [t for t in triples if t[2] == "EMAIL"]
    assert len(emails) >= 1
    assert len({(s, e) for s, e, _ in emails}) == 1
