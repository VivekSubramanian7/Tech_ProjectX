"""Append-only audit log writer."""

from __future__ import annotations

import sqlite3

from app.repositories import CatalogRepository


def audit_finding_created(
    repo: CatalogRepository,
    conn: sqlite3.Connection,
    *,
    finding_id: int,
    detector_version: str | None,
    model_version: str | None = None,
    prompt_hash: str | None = None,
) -> None:
    repo.append_audit(
        conn,
        entity_type="finding",
        entity_id=str(finding_id),
        action="created",
        detector_version=detector_version,
        model_version=model_version,
        prompt_hash=prompt_hash,
    )
