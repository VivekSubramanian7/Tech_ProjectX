"""Run the Tier-1 engine over an eval corpus and return harness Finding objects.

Two corpora are supported:
- the seed set under `data/samples` (default), and
- the large/multi-format corpus under `data/corpus`, scanned through a *filtered*
  source so `native_id`s stay relative to `data/corpus` (e.g. "text/hr/x.txt",
  "docx/hr/x.docx") and therefore line up with the corpus_large labels.
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any, Iterator, Sequence

from contracts import Finding, Span
from eval_config import EVAL_SCOPE_ID, eval_corpus_root

_REPO_ROOT = Path(__file__).resolve().parents[1]


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


def _engine_findings(target: Any, *, scope_id: str) -> list[Finding]:
    """Set up a throwaway catalog, scan `target` (a Path or FileSource), map findings."""
    from app.repositories import CatalogRepository
    from app.services.scan_orchestrator import ScanOrchestrator

    seed = _REPO_ROOT / "data" / "enum_seed.sql"
    owners = _REPO_ROOT / "data" / "mock_owners.json"

    scratch = _REPO_ROOT / "data" / f".eval_catalog_{uuid.uuid4().hex}.sqlite"
    if scratch.exists():
        try:
            scratch.unlink()
        except OSError:
            pass

    repo = CatalogRepository(scratch)
    try:
        repo.init_db(seed if seed.is_file() else None)
        orch = ScanOrchestrator(repo, ownership_map_path=owners if owners.is_file() else None)
        raw_findings = orch.run_scan(target, scope_id=scope_id, mode="full")["findings"]
        return [finding_from_engine_dict(d) for d in raw_findings if "span" in d]
    finally:
        for _ in range(5):
            try:
                if scratch.exists():
                    scratch.unlink()
                break
            except OSError:
                time.sleep(0.05)


def collect_findings(
    corpus_root: Path | None = None,
    *,
    scope_id: str = EVAL_SCOPE_ID,
) -> list[Finding]:
    """Scan a folder with the Tier-1 pipeline; return findings (text files only)."""
    root = (corpus_root or eval_corpus_root()).resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"eval corpus not found: {root}")
    return _engine_findings(root, scope_id=scope_id)


def _subtree_source(prefixes: Sequence[str], scope_id: str):
    """A LocalFolderSource over data/corpus that only yields files whose native_id
    starts with one of `prefixes` (e.g. "text/", "docx/"). native_id stays relative
    to data/corpus so it matches the corpus_large labels."""
    from app.sources.local_folder import LocalFolderSource

    from corpus_large import corpus_root

    allowed = tuple(prefixes)

    class _Subtree(LocalFolderSource):
        def iter_files(self) -> Iterator:
            for ref in super().iter_files():
                if ref.native_id.startswith(allowed):
                    yield ref

    return _Subtree(corpus_root(), scope_id=scope_id)


def collect_corpus_findings(
    prefixes: Sequence[str],
    *,
    scope_id: str,
) -> list[Finding]:
    """Scan the data/corpus subtree(s) under `prefixes` with the Tier-1 pipeline."""
    from corpus_large import corpus_root

    if not corpus_root().is_dir():
        raise FileNotFoundError(f"corpus not found: {corpus_root()}")
    return _engine_findings(_subtree_source(prefixes, scope_id), scope_id=scope_id)
