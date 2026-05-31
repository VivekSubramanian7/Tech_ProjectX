"""Shared constants for the eval corpus and labeled-set file identity."""

from __future__ import annotations

from pathlib import Path

EVAL_SOURCE_TYPE = "local"
EVAL_SCOPE_ID = "gdpr-eval-samples-v1"


def eval_file_id(native_id: str) -> str:
    """sha256(source_type:scope_id:native_id) — matches engine with fixed eval scope."""
    from app.identity import file_id

    return file_id(EVAL_SOURCE_TYPE, EVAL_SCOPE_ID, native_id)


def eval_corpus_root() -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "samples"
