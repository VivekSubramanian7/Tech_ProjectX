"""Ensure data/samples text files match labeled span offsets (Story 2.1 corpus)."""

from __future__ import annotations

import re

from contracts import Span
from eval_config import eval_corpus_root
from labeled_set import load_labeled_set

_SHAPE_HINTS: dict[str, re.Pattern[str]] = {
    "EMAIL": re.compile(r"@"),
    "IBAN": re.compile(r"^DE", re.IGNORECASE),
    "IP_ADDRESS": re.compile(r"^\d+\.\d+\.\d+\.\d+"),
    "PHONE_NUMBER": re.compile(r"\+?\d"),
}


def test_text_labels_have_on_disk_corpus_with_valid_spans():
    root = eval_corpus_root()
    assert root.is_dir(), f"missing eval corpus at {root}"

    for label in load_labeled_set():
        if label.modality != "text":
            continue
        assert isinstance(label.location, Span)
        path = root / label.native_id
        assert path.is_file(), f"missing corpus file {path}"
        content = path.read_text(encoding="utf-8")
        assert len(content) >= label.location.end, (
            f"{label.native_id}: content length {len(content)} < span end {label.location.end}"
        )
        snippet = content[label.location.start : label.location.end]
        assert snippet.strip(), (
            f"{label.native_id}: empty span [{label.location.start}:{label.location.end})"
        )
        hint = _SHAPE_HINTS.get(label.classification_code)
        if hint:
            assert hint.search(snippet), (
                f"{label.native_id} {label.classification_code}: unexpected snippet {snippet!r}"
            )
