"""Scan trigger API."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.repositories import CatalogRepository
from app.scan_config import ScanConfig, ScanOptions, load_scan_config, resolve_scan_source
from app.services.scan_orchestrator import ScanOrchestrator

router = APIRouter(prefix="/scans", tags=["scans"])

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB = ROOT / "data" / "catalog.sqlite"
SEED_SQL = ROOT / "data" / "enum_seed.sql"

_shared_repo = CatalogRepository(DEFAULT_DB)
_shared_orch = ScanOrchestrator(_shared_repo)


class ScanRequest(BaseModel):
    path: str | None = Field(None, description="Local folder path (overrides config path)")
    mode: Literal["full", "delta"] = Field("full", description="full or delta scan")
    tier2: bool = Field(False, description="Apply Tier-2 escalation after Tier-1")
    reapply_ruleset: bool = Field(False, description="Re-scan stale ruleset files in delta mode")
    use_config: bool = Field(True, description="Load defaults from config/scan.yaml")
    use_ml_image: bool | None = Field(
        None, description="Enable YOLO/EasyOCR image detectors (defaults from scan.yaml or true)"
    )
    use_spacy: bool | None = Field(None, description="Enable spaCy NER (defaults from scan.yaml or false)")


def _resolve_scan_options(body: ScanRequest) -> ScanOptions:
    """Merge API body flags with scan.yaml when present."""
    cfg: ScanConfig | None = None
    if body.use_config:
        try:
            cfg = load_scan_config()
        except FileNotFoundError:
            cfg = None

    use_ml = body.use_ml_image if body.use_ml_image is not None else (cfg.use_ml_image if cfg else True)
    use_spacy = body.use_spacy if body.use_spacy is not None else (cfg.use_spacy if cfg else False)
    return ScanOptions(use_spacy=use_spacy, use_ml_image=use_ml)


@router.post("")
def create_scan(body: ScanRequest) -> dict:
    _shared_repo.init_db(SEED_SQL if SEED_SQL.is_file() else None)

    if body.use_config and not body.path:
        cfg = load_scan_config()
        if body.mode != "full" or body.tier2 or body.reapply_ruleset:
            cfg = ScanConfig(
                path=cfg.path,
                scope_id=cfg.scope_id,
                mode=body.mode if body.mode != "full" else cfg.mode,
                tier2=body.tier2 or cfg.tier2,
                reapply_ruleset=body.reapply_ruleset or cfg.reapply_ruleset,
                source=cfg.source,
                onedrive_fixture=cfg.onedrive_fixture,
                use_spacy=cfg.use_spacy,
                use_ml_image=cfg.use_ml_image,
            )
        target = resolve_scan_source(cfg)
        scope_id = cfg.scope_id
        mode = cfg.mode
        tier2 = cfg.tier2
        reapply = cfg.reapply_ruleset
        options = _resolve_scan_options(body)
    else:
        folder = Path(body.path or "")
        if not folder.is_dir():
            raise HTTPException(status_code=400, detail="path must be an existing directory")
        target = folder
        scope_id = None
        mode = body.mode
        tier2 = body.tier2
        reapply = body.reapply_ruleset
        options = _resolve_scan_options(body)

    scan_id = _shared_orch.begin_scan(
        target,
        scope_id=scope_id,
        mode=mode,
        reapply_ruleset=reapply,
        tier2=tier2,
        options=options,
    )
    status = _shared_orch.get_scan_status(scan_id)
    return {"data": status, "meta": {"scan_id": scan_id, "mode": mode}}


@router.get("")
def list_scans() -> dict:
    _shared_repo.init_db(SEED_SQL if SEED_SQL.is_file() else None)
    with _shared_repo.connect() as conn:
        rows = conn.execute(
            "SELECT scan_id, scope_id, mode, status, files_total, files_scanned, "
            "findings_count, tier2_applied, started_ts, completed_ts, ruleset_version, "
            "total_bytes, duration_ms, type_breakdown "
            "FROM scan_run ORDER BY started_ts DESC"
        ).fetchall()

    out = []
    for r in rows:
        d = dict(r)
        raw = d.pop("type_breakdown", None)
        try:
            d["type_breakdown"] = json.loads(raw) if raw else None
        except (TypeError, ValueError):
            d["type_breakdown"] = None
        out.append(d)
    return {"data": out}


@router.get("/{scan_id}")
def get_scan(scan_id: str) -> dict:
    try:
        status = _shared_orch.get_scan_status(scan_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="scan not found") from None
    return {"data": status}
