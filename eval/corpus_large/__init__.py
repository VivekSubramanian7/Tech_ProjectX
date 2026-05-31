"""Large labeled text corpus + loader.

A separate, deterministically generated dataset that reuses the harness contracts
(`Span`, `Label`) and enum codes. The hand-curated seed set at `eval/labeled_set/`
is untouched; this is the high-volume set for real accuracy numbers.

Data lives next to this module:
- `labels.jsonl` — one span-level label per line
- `manifest.yaml` — seed, provenance, distribution, counts
- `generate.py`   — regenerates files + labels deterministically

Corpus files live under `data/corpus/`; `native_id` is the path relative to that root.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from contracts import BBox, EntityLabel, Label, Location, Span

_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _DIR.parents[1]
_LABELS_FILE = _DIR / "labels.jsonl"
_MANIFEST_FILE = _DIR / "manifest.yaml"
_ENTITY_LABELS_FILE = _DIR / "labels_entity.jsonl"
_MULTIFORMAT_MANIFEST_FILE = _DIR / "manifest_multiformat.yaml"

# Distinct eval scope so file_ids never collide with the seed set.
CORPUS_SOURCE_TYPE = "local"
CORPUS_SCOPE_ID = "gdpr-eval-corpus-large-v1"


def corpus_root() -> Path:
    """Root the `native_id` paths resolve against (data/corpus)."""
    return _REPO_ROOT / "data" / "corpus"


def corpus_file_id(native_id: str) -> str:
    """sha256(source_type:scope_id:native_id) — matches the engine's identity scheme."""
    from app.identity import file_id

    return file_id(CORPUS_SOURCE_TYPE, CORPUS_SCOPE_ID, native_id)


def _parse_location(raw: dict[str, Any]) -> Location:
    kind = raw["type"]
    if kind == "span":
        return Span(start=raw["start"], end=raw["end"])
    if kind == "bbox":
        return BBox(x=raw["x"], y=raw["y"], w=raw["w"], h=raw["h"])
    raise ValueError(f"unknown location type {kind!r}")


def load_corpus_labels() -> list[Label]:
    """Load every ground-truth label from labels.jsonl."""
    labels: list[Label] = []
    for line in _LABELS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        native_id = row["native_id"]
        labels.append(
            Label(
                file_id=corpus_file_id(native_id),
                native_id=native_id,
                classification_code=row["classification_code"],
                modality=row["modality"],
                location=_parse_location(row["location"]),
                provenance=row["provenance"],
            )
        )
    return labels


def load_corpus_manifest() -> dict[str, Any]:
    """Load the corpus manifest (provenance, seed, distribution, counts)."""
    return yaml.safe_load(_MANIFEST_FILE.read_text(encoding="utf-8"))


def load_entity_labels() -> list[EntityLabel]:
    """Load the multi-format (.docx/.pdf) entity-level ground truth."""
    labels: list[EntityLabel] = []
    for line in _ENTITY_LABELS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        native_id = row["native_id"]
        labels.append(
            EntityLabel(
                file_id=corpus_file_id(native_id),
                native_id=native_id,
                classification_code=row["classification_code"],
                modality=row["modality"],
                occurrence=row["occurrence"],
                provenance=row["provenance"],
                file_format=row["file_format"],
            )
        )
    return labels


def load_multiformat_manifest() -> dict[str, Any]:
    """Load the multi-format corpus manifest."""
    return yaml.safe_load(_MULTIFORMAT_MANIFEST_FILE.read_text(encoding="utf-8"))


def canonical_sidecar_path(native_id: str) -> Path:
    """Path to the canonical extracted-text sidecar for a docx/pdf native_id.

    e.g. "docx/hr/hr_record_0000.docx" -> data/corpus/canonical/docx/hr/hr_record_0000.txt
    """
    fmt, rest = native_id.split("/", 1)
    stem = rest.rsplit(".", 1)[0]
    return corpus_root() / "canonical" / fmt / f"{stem}.txt"
