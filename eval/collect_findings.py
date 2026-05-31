"""Run Tier-1 engine over the eval corpus and return harness Finding objects."""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any

from contracts import Finding, Span
from eval_config import EVAL_SCOPE_ID, eval_corpus_root


def finding_from_engine_dict(raw: dict[str, Any]) -> Finding:
    """Map orchestrator canonical finding dict to eval contracts.Finding."""
    span = raw["span"]
    return Finding(
        file_id=raw["file_id"],
        classification_code=raw["code"],
        modality="text",
        location=Span(start=span[0], end=span[1]),
        confidence_score=float(raw["confidence"]),
        risk_weight=raw["risk_weight"],
    )


def collect_findings(
    corpus_root: Path | None = None,
    *,
    scope_id: str = EVAL_SCOPE_ID,
) -> list[Finding]:
    """Scan eval corpus with Tier-1 text pipeline; return findings (text files only)."""
    root = (corpus_root or eval_corpus_root()).resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"eval corpus not found: {root}")

    from app.repositories import CatalogRepository
    from app.services.scan_orchestrator import ScanOrchestrator

    repo_root = root.parents[1]
    seed = repo_root / "data" / "enum_seed.sql"
    owners = repo_root / "data" / "mock_owners.json"

    scratch = repo_root / "data" / f".eval_catalog_{uuid.uuid4().hex}.sqlite"
    if scratch.exists():
        try:
            scratch.unlink()
        except OSError:
            pass

    repo = CatalogRepository(scratch)
    try:
        repo.init_db(seed if seed.is_file() else None)
        orch = ScanOrchestrator(repo, ownership_map_path=owners if owners.is_file() else None)
        raw_findings = orch.tier1_scan_callable(root, scope_id=scope_id)()
        return [finding_from_engine_dict(d) for d in raw_findings]
    finally:
        for _ in range(5):
            try:
                if scratch.exists():
                    scratch.unlink()
                break
            except OSError:
                time.sleep(0.05)
