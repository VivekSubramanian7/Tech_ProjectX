"""Text extraction tests."""

import io
import zipfile
from pathlib import Path

from app.detectors.text.extract import extract_docx_bytes, extract_file, extract_plain_text, segments_from_text
from app.detectors.text.regex_checksum import RegexChecksumDetector

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


def _minimal_docx(text: str) -> bytes:
    document_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>{text}</w:t></w:r></w:p>
  </w:body>
</w:document>"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("word/document.xml", document_xml)
    return buf.getvalue()


def test_extract_docx_bytes():
    data = _minimal_docx("Contact: test@example.com")
    text = extract_docx_bytes(data)
    assert "test@example.com" in text


def test_extract_file_docx(tmp_path: Path):
    path = tmp_path / "note.docx"
    path.write_bytes(_minimal_docx("Email: user@corp.de"))
    with path.open("rb") as f:
        segments, content_hash = extract_file(str(path), f)
    joined = "".join(s.text for s in segments)
    assert "user@corp.de" in joined
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
