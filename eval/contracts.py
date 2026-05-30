"""Shared eval-harness contracts.

These frozen dataclasses are the stable interface between the scan engine and the
evaluation harness. Epic 1's engine will later emit `Finding`s conforming to this
shape; the harness (Stories 2.2/2.3) compares them against ground-truth `Label`s.

GDPR invariant: neither a Label nor a Finding ever carries a raw PII value — only
a classification code, a location, and (for findings) a confidence score.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Span:
    """A character span within a text document (half-open: [start, end))."""

    start: int
    end: int


@dataclass(frozen=True)
class BBox:
    """A pixel bounding box within an image."""

    x: int
    y: int
    w: int
    h: int


# A location is either a text span or an image bounding box.
Location = Span | BBox


@dataclass(frozen=True)
class Label:
    """A piece of ground truth: this file contains this PII at this location."""

    file_id: str
    classification_code: str
    modality: str  # "text" | "image"
    location: Location
    provenance: str  # where this annotation came from (audit / inter-annotator)


@dataclass(frozen=True)
class Finding:
    """The engine's output for one detected entity (no raw PII value)."""

    file_id: str
    classification_code: str
    modality: str
    location: Location
    confidence_score: float
    risk_weight: str  # "Critical" | "High" | "Medium" | "Low" (from the enum)
