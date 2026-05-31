"""Scan trigger API."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.repositories import CatalogRepository
from app.scan_config import ScanConfig, load_scan_config, resolve_scan_source, scan_options_from_config
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
        options = scan_options_from_config(cfg)
    else:
        folder = Path(body.path or "")
        if not folder.is_dir():
            raise HTTPException(status_code=400, detail="path must be an existing directory")
        target = folder
        scope_id = None
        mode = body.mode
        tier2 = body.tier2
        reapply = body.reapply_ruleset
        options = None

    scan_id = _shared_orch.start_scan(
        target,
        scope_id=scope_id,
        mode=mode,
        reapply_ruleset=reapply,
        tier2=tier2,
        options=options,
    )
    status = _shared_orch.get_scan_status(scan_id)
    return {"data": status, "meta": {"scan_id": scan_id, "mode": mode}}


@router.get("/{scan_id}")
def get_scan(scan_id: str) -> dict:
    try:
        status = _shared_orch.get_scan_status(scan_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="scan not found") from None
    return {"data": status}
