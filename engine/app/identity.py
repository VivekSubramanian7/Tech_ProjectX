"""Deterministic file identity."""

from __future__ import annotations

import hashlib


def file_id(source_type: str, scope_id: str, native_id: str) -> str:
    """sha256(source_type:scope_id:native_id) — never random."""
    payload = f"{source_type}:{scope_id}:{native_id}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
