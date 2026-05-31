"""Wiring tests: the large/multiformat corpora plug into the eval harness.

The fast tests assert *identity alignment* — the filtered source's file_ids match
the corpus labels' file_ids — without running the engine. The slow test actually
scans a tiny subtree end-to-end.
"""
from __future__ import annotations

import pytest

from corpus_large import (
    CORPUS_SCOPE_ID,
    corpus_file_id,
    load_corpus_labels,
    load_entity_labels,
)


def test_filtered_source_native_ids_match_text_labels():
    from collect_findings import _subtree_source

    src = _subtree_source(("text/",), CORPUS_SCOPE_ID)
    refs = list(src.iter_files())
    assert refs, "no text files yielded"
    # every yielded file is under text/ and identity-aligns with a corpus label
    assert all(r.native_id.startswith("text/") for r in refs)
    src_file_ids = {corpus_file_id(r.native_id) for r in refs}
    label_file_ids = {l.file_id for l in load_corpus_labels()}
    assert label_file_ids <= src_file_ids, "some labeled files are not scannable"


def test_filtered_source_excludes_other_formats():
    from collect_findings import _subtree_source

    src = _subtree_source(("docx/", "pdf/"), CORPUS_SCOPE_ID)
    refs = list(src.iter_files())
    assert refs
    assert all(r.native_id.startswith(("docx/", "pdf/")) for r in refs)
    # entity labels for docx/pdf must all be scannable
    src_ids = {corpus_file_id(r.native_id) for r in refs}
    assert {l.file_id for l in load_entity_labels()} <= src_ids


def test_source_scope_matches_loader_scope():
    from collect_findings import _subtree_source

    src = _subtree_source(("text/",), CORPUS_SCOPE_ID)
    # the FileRef scope_id the engine hashes must equal the loader's scope
    ref = next(iter(src.iter_files()))
    assert ref.scope_id == CORPUS_SCOPE_ID
    assert corpus_file_id(ref.native_id) == ref_file_id(ref)


def ref_file_id(ref) -> str:
    from app.identity import file_id

    return file_id(ref.source_type, ref.scope_id, ref.native_id)


@pytest.mark.slow
def test_engine_scans_corpus_subtree_and_aligns(tmp_path):
    """End-to-end on ~10 files: findings carry file_ids that exist in the labels."""
    try:
        from collect_findings import _engine_findings, _subtree_source
    except ImportError:
        pytest.skip("engine not available")

    # one HR template's files only -> small, fast
    src = _subtree_source(("text/hr/hr_record_000",), CORPUS_SCOPE_ID)
    try:
        findings = _engine_findings(src, scope_id=CORPUS_SCOPE_ID)
    except ImportError:
        pytest.skip("engine package not on PYTHONPATH")

    label_ids = {l.file_id for l in load_corpus_labels()}
    assert findings, "engine produced no findings on the HR subtree"
    assert any(f.file_id in label_ids for f in findings)
