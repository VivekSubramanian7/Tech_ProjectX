"""Tests for the multi-format (.docx/.pdf) corpus (Phase 2).

Ground truth is entity-level (no spans). We assert the rendered files and their
canonical-text sidecars exist, the labels cover all text codes, the manifest
distribution is consistent, and regeneration of the labels + sidecars is
deterministic.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from enum_ref import ENUM
from corpus_large import (
    canonical_sidecar_path,
    corpus_root,
    load_entity_labels,
    load_multiformat_manifest,
)

_TEXT_CODES = {c for c, meta in ENUM.items() if meta["modality"] == "text"}
_DIR = Path(__file__).resolve().parent / "corpus_large"
_ENTITY_FILE = _DIR / "labels_entity.jsonl"
_CANON_ROOT = corpus_root() / "canonical"


def test_both_formats_are_present() -> None:
    docx = list((corpus_root() / "docx").rglob("*.docx"))
    pdf = list((corpus_root() / "pdf").rglob("*.pdf"))
    assert len(docx) >= 250, len(docx)
    assert len(pdf) >= 250, len(pdf)


def test_entity_labels_are_plentiful() -> None:
    assert len(load_entity_labels()) >= 800


def test_entity_labels_use_known_text_codes_and_formats() -> None:
    for label in load_entity_labels():
        assert label.classification_code in _TEXT_CODES, label.classification_code
        assert label.file_format in {"docx", "pdf"}
        assert label.occurrence >= 0
        assert label.provenance == "synthetic/generator"


def test_every_text_code_is_represented() -> None:
    seen = {label.classification_code for label in load_entity_labels()}
    assert not (_TEXT_CODES - seen), f"missing: {sorted(_TEXT_CODES - seen)}"


def test_rendered_files_and_sidecars_exist() -> None:
    root = corpus_root()
    for label in load_entity_labels():
        assert (root / label.native_id).is_file(), label.native_id
        sidecar = canonical_sidecar_path(label.native_id)
        assert sidecar.is_file(), f"missing canonical sidecar for {label.native_id}"
        assert sidecar.read_text(encoding="utf-8").strip()


def test_rendered_files_are_well_formed() -> None:
    """Spot-check one docx and one pdf actually parse as their format."""
    import docx as _docx

    root = corpus_root()
    a_docx = next(iter((root / "docx").rglob("*.docx")))
    doc = _docx.Document(str(a_docx))
    assert any(p.text.strip() for p in doc.paragraphs)

    a_pdf = next(iter((root / "pdf").rglob("*.pdf")))
    assert a_pdf.read_bytes().startswith(b"%PDF-")


def test_manifest_distribution_matches_labels() -> None:
    labels = load_entity_labels()
    manifest = load_multiformat_manifest()
    by_cat = manifest["distribution"]["by_category"]
    assert sum(by_cat.values()) == len(labels)
    by_fmt = manifest["distribution"]["by_format"]
    assert sum(by_fmt.values()) == manifest["counts"]["files"]


def test_manifest_records_seed_and_lib_versions() -> None:
    prov = load_multiformat_manifest()["provenance"]
    assert isinstance(prov["master_seed"], int)
    assert prov["python_docx_version"]
    assert prov["reportlab_version"]
    assert load_multiformat_manifest()["granularity"] == "entity"


def test_decoys_present_for_false_positive_measurement() -> None:
    counts = load_multiformat_manifest()["counts"]
    assert counts["decoy_files"] >= 0.2 * counts["files"]


@pytest.mark.slow
def test_regeneration_is_deterministic() -> None:
    """Labels + canonical sidecars regenerate byte-identically (binaries may carry
    format metadata, so determinism is asserted on the ground-truth artifacts)."""
    import hashlib

    from corpus_large import generate_multiformat

    def digest() -> str:
        h = hashlib.sha256()
        h.update(_ENTITY_FILE.read_bytes())
        for p in sorted(_CANON_ROOT.rglob("*.txt")):
            h.update(p.read_bytes())
        return h.hexdigest()

    before = digest()
    generate_multiformat.generate()
    assert digest() == before, "entity labels / canonical sidecars are non-deterministic"
