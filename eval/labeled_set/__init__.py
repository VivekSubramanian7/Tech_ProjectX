"""Labeled evaluation set + loader (Story 2.1).

The ground truth the harness scores against. Data lives next to this module:
- `labels.jsonl` — one label per line (file_id, classification_code, modality, location, provenance)
- `manifest.yaml` — provenance, inter-annotator agreement (Cohen's kappa), and distribution

This seed set nails the FORMAT and the loader; volume grows toward the manifest's
`target_size` (200 text entities + 50 images).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from contracts import BBox, Label, Location, Span

_DIR = Path(__file__).parent
_LABELS_FILE = _DIR / "labels.jsonl"
_MANIFEST_FILE = _DIR / "manifest.yaml"


def _parse_location(raw: dict[str, Any]) -> Location:
    kind = raw["type"]
    if kind == "span":
        return Span(start=raw["start"], end=raw["end"])
    if kind == "bbox":
        return BBox(x=raw["x"], y=raw["y"], w=raw["w"], h=raw["h"])
    raise ValueError(f"unknown location type {kind!r}")


def load_labeled_set() -> list[Label]:
    """Load every ground-truth label from labels.jsonl."""
    labels: list[Label] = []
    for line in _LABELS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        labels.append(
            Label(
                file_id=row["file_id"],
                classification_code=row["classification_code"],
                modality=row["modality"],
                location=_parse_location(row["location"]),
                provenance=row["provenance"],
            )
        )
    return labels


def load_manifest() -> dict[str, Any]:
    """Load the eval-set manifest (provenance, kappa, distribution)."""
    return yaml.safe_load(_MANIFEST_FILE.read_text(encoding="utf-8"))
