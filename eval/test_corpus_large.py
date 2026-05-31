"""Tests for the large labeled text corpus (eval/corpus_large).

Mirrors the seed-set tests (test_labeled_set.py / test_corpus_alignment.py) but at
volume, and adds a determinism guard: regenerating from the master seed must
reproduce byte-identical labels.

Marked `slow` only where it regenerates the corpus.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from contracts import Span
from enum_ref import ENUM
from corpus_large import (
    CORPUS_SCOPE_ID,
    corpus_file_id,
    corpus_root,
    load_corpus_labels,
    load_corpus_manifest,
)

_SHAPE_HINTS: dict[str, re.Pattern[str]] = {
    "EMAIL": re.compile(r"@"),
    "IBAN": re.compile(r"^DE", re.IGNORECASE),
    "IP_ADDRESS": re.compile(r"^\d+\.\d+\.\d+\.\d+"),
    "PHONE_NUMBER": re.compile(r"\+?\d"),
}

# text-modality codes only — the corpus is text-only by design
_TEXT_CODES = {c for c, meta in ENUM.items() if meta["modality"] == "text"}
_LABELS_FILE = Path(__file__).resolve().parent / "corpus_large" / "labels.jsonl"


def test_corpus_is_large() -> None:
    files = list((corpus_root() / "text").rglob("*.txt"))
    assert len(files) >= 1000, f"expected >=1000 files, got {len(files)}"


def test_labels_are_plentiful() -> None:
    assert len(load_corpus_labels()) >= 1000


def test_every_label_uses_a_known_text_enum_code() -> None:
    for label in load_corpus_labels():
        assert label.classification_code in _TEXT_CODES, label.classification_code


def test_every_text_code_is_represented() -> None:
    seen = {label.classification_code for label in load_corpus_labels()}
    missing = _TEXT_CODES - seen
    assert not missing, f"text codes never labeled: {sorted(missing)}"


def test_spans_align_with_on_disk_files() -> None:
    root = corpus_root()
    for label in load_corpus_labels():
        assert isinstance(label.location, Span)
        path = root / label.native_id
        assert path.is_file(), f"missing corpus file {path}"
        content = path.read_text(encoding="utf-8")
        assert len(content) >= label.location.end
        snippet = content[label.location.start : label.location.end]
        assert snippet.strip(), f"{label.native_id}: empty span"
        hint = _SHAPE_HINTS.get(label.classification_code)
        if hint:
            assert hint.search(snippet), (
                f"{label.native_id} {label.classification_code}: {snippet!r}"
            )


def test_every_label_has_generator_provenance() -> None:
    for label in load_corpus_labels():
        assert label.provenance == "synthetic/generator"


def test_manifest_distribution_matches_label_counts() -> None:
    labels = load_corpus_labels()
    dist = load_corpus_manifest()["distribution"]
    assert sum(dist["by_modality"].values()) == len(labels)
    assert sum(dist["by_category"].values()) == len(labels)


def test_manifest_records_seed_and_provenance() -> None:
    prov = load_corpus_manifest()["provenance"]
    assert prov["annotation"] == "synthetic/generator"
    assert isinstance(prov["master_seed"], int)
    assert prov["faker_locale"] == "de_DE"


def test_decoy_files_exist_for_false_positive_measurement() -> None:
    counts = load_corpus_manifest()["counts"]
    assert counts["decoy_files"] > 0
    # decoys should be a meaningful slice (~40%), not a token few
    assert counts["decoy_files"] >= 0.2 * counts["files"]


def test_corpus_file_id_is_stable_sha256_and_scoped() -> None:
    fid = corpus_file_id("text/hr/hr_record_0000.txt")
    assert len(fid) == 64 and all(c in "0123456789abcdef" for c in fid)
    assert CORPUS_SCOPE_ID == "gdpr-eval-corpus-large-v1"


@pytest.mark.slow
def test_regeneration_is_deterministic() -> None:
    """Regenerating from the master seed reproduces identical labels.jsonl."""
    before = _LABELS_FILE.read_bytes()
    from corpus_large import generate

    generate.generate()
    after = _LABELS_FILE.read_bytes()
    assert before == after, "regeneration changed labels.jsonl — non-deterministic!"
