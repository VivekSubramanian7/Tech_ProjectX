"""Text extraction with segment streaming and incremental hashing."""

from __future__ import annotations

import hashlib
import io
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Iterator

from app.config import CHUNK_SIZE, OVERLAP_CHARS

_DOCX_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


@dataclass(frozen=True)
class TextSegment:
    text: str
    base_offset: int
    page: int | None = None


def incremental_sha256(stream: BinaryIO, chunk_size: int = CHUNK_SIZE) -> str:
    h = hashlib.sha256()
    while True:
        chunk = stream.read(chunk_size)
        if not chunk:
            break
        h.update(chunk)
    return h.hexdigest()


def segments_from_text(
    full_text: str,
    *,
    chunk_chars: int = 4096,
    overlap: int = OVERLAP_CHARS,
) -> Iterator[TextSegment]:
    """Yield overlapping segments with global offsets."""
    if not full_text:
        return
    start = 0
    n = len(full_text)
    while start < n:
        end = min(start + chunk_chars, n)
        yield TextSegment(text=full_text[start:end], base_offset=start)
        if end >= n:
            break
        start = end - overlap


def extract_plain_text(stream: BinaryIO, suffix: str) -> tuple[str, str]:
    """Read text file; return (text, content_hash)."""
    if hasattr(stream, "readall"):
        data = stream.readall()
    else:
        data = stream.read()
    content_hash = hashlib.sha256(data).hexdigest()
    text = data.decode("utf-8", errors="replace")
    return text, content_hash


def extract_docx_bytes(data: bytes) -> str:
    """Extract paragraph text from a .docx (OOXML zip) using stdlib only."""
    parts: list[str] = []
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        if "word/document.xml" not in zf.namelist():
            return ""
        root = ET.fromstring(zf.read("word/document.xml"))
        for para in root.findall(".//w:p", _DOCX_NS):
            runs = [node.text for node in para.findall(".//w:t", _DOCX_NS) if node.text]
            if runs:
                parts.append("".join(runs))
    return "\n".join(parts)


def extract_file(ref_path: str, stream: BinaryIO) -> tuple[Iterator[TextSegment], str]:
    path = Path(ref_path)
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _extract_pdf(stream)
    if suffix == ".docx":
        return _extract_docx(stream)
    text, content_hash = extract_plain_text(stream, suffix)
    return segments_from_text(text), content_hash


def _extract_docx(stream: BinaryIO) -> tuple[Iterator[TextSegment], str]:
    data = stream.readall() if hasattr(stream, "readall") else stream.read()
    content_hash = hashlib.sha256(data).hexdigest()
    text = extract_docx_bytes(data)
    return segments_from_text(text), content_hash


def _extract_pdf(stream: BinaryIO) -> tuple[Iterator[TextSegment], str]:
    content_hash = incremental_sha256(stream)
    try:
        from pypdf import PdfReader
    except ImportError:
        return iter([]), content_hash

    if hasattr(stream, "seek"):
        stream.seek(0)
    reader = PdfReader(stream)

    def _gen() -> Iterator[TextSegment]:
        offset = 0
        for page_num, page in enumerate(reader.pages, start=1):
            page_text = page.extract_text() or ""
            for seg in segments_from_text(page_text):
                yield TextSegment(
                    text=seg.text,
                    base_offset=offset + seg.base_offset,
                    page=page_num,
                )
            offset += len(page_text)

    return _gen(), content_hash


def merge_detections_with_overlap(
    all_detections: list[tuple[int, int, object]],
) -> list[object]:
    """Dedupe detections that appear in overlap windows (same span)."""
    seen: set[tuple[int, int, str]] = set()
    out: list[object] = []
    for start, end, det in sorted(all_detections, key=lambda x: (x[0], x[1])):
        code = getattr(det, "classification_code", "")
        key = (start, end, code)
        if key in seen:
            continue
        seen.add(key)
        out.append(det)
    return out
