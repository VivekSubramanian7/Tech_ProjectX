"""Modality router — text vs image vs OCR paths (Story 3.1)."""

from __future__ import annotations

from enum import Enum
from pathlib import Path


class Modality(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    OCR = "ocr"


_TEXT_EXTENSIONS = {".txt", ".csv", ".md", ".log", ".docx", ".doc", ".rtf"}
_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff", ".tif"}


def route_file(path: str, *, magic: bytes | None = None) -> Modality:
    """Classify a file path (and optional leading bytes) into a scan modality."""
    suffix = Path(path).suffix.lower()
    if suffix in _TEXT_EXTENSIONS:
        return Modality.TEXT
    if suffix in _IMAGE_EXTENSIONS:
        return Modality.IMAGE
    if suffix == ".pdf":
        return _route_pdf(magic)
    if suffix:
        return Modality.TEXT
    return Modality.TEXT


def scannable_extensions() -> frozenset[str]:
    """File extensions the scan pipeline handles."""
    return frozenset(
        {
            ".txt",
            ".csv",
            ".md",
            ".log",
            ".docx",
            ".doc",
            ".rtf",
            ".pdf",
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".webp",
            ".bmp",
            ".tiff",
            ".tif",
        }
    )


def is_scannable_path(path: str) -> bool:
    return Path(path).suffix.lower() in scannable_extensions()


def _route_pdf(magic: bytes | None) -> Modality:
    if magic is None:
        return Modality.OCR
    head = magic[:512].lower()
    if b" bt " in head or b"/font" in head or b"(hello)" in head:
        return Modality.TEXT
    if b"scanned" in head or b"/image" in head:
        return Modality.OCR
    return Modality.OCR
