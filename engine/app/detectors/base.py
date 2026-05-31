"""Detector protocol and shared types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class TextSpan:
    start: int
    end: int


@dataclass(frozen=True)
class Detection:
    classification_code: str
    span: TextSpan
    confidence_score: float
    masked_snippet: str
    detector_version: str
    model_version: str | None = None


@dataclass(frozen=True)
class BBox:
    x: float
    y: float
    w: float
    h: float


@dataclass(frozen=True)
class ImageDetection:
    classification_code: str
    bbox: BBox
    confidence_score: float
    masked_snippet: str
    detector_version: str
    model_version: str | None = None


class TextDetector(Protocol):
    detector_version: str

    def detect(self, text: str, base_offset: int = 0) -> list[Detection]:
        ...


def mask_value(value: str, visible_tail: int = 4) -> str:
    if len(value) <= visible_tail:
        return "•" * len(value)
    return "•" * (len(value) - visible_tail) + value[-visible_tail:]
