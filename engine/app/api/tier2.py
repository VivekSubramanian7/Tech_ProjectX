"""Explicit Tier-2 confirmation pass API.

Admin triggers a Tier-2 pass over already-scanned open findings.
Runs in a background daemon thread; Admin polls for status.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.api import scans as scans_api

router = APIRouter(prefix="/tier2", tags=["tier2"])

ROOT = Path(__file__).resolve().parents[3]
SEED_SQL = ROOT / "data" / "enum_seed.sql"


class Tier2RunRequest(BaseModel):
    scope_id: str | None = Field(None, description="Limit to a specific scan scope (optional)")
    budget: int | None = Field(None, description="Max Tier-2 escalations for this pass (defaults to TIER2_BUDGET env or 100)")


@router.post("/run")
def run_tier2(body: Tier2RunRequest) -> dict:
    """Start an explicit Tier-2 confirmation pass in the background.

    Returns immediately with a job_id. Poll GET /tier2/run for progress.
    Returns 409 if a scan or another Tier-2 pass is already active.
    """
    scans_api._shared_repo.init_db(SEED_SQL if SEED_SQL.is_file() else None)

    if scans_api._shared_orch.has_active_scan():
        raise HTTPException(status_code=409, detail="Cannot start Tier-2 pass while a scan is in progress")

    if scans_api._shared_orch.has_active_tier2_pass():
        raise HTTPException(status_code=409, detail="A Tier-2 pass is already running")

    job_id = scans_api._shared_orch.begin_tier2_pass(
        scope_id=body.scope_id,
        budget=body.budget,
    )
    return {
        "data": {"job_id": job_id, "status": "running"},
        "meta": {"job_id": job_id},
    }


@router.get("/run")
def get_tier2_status() -> dict:
    """Return the status of the most recent (or active) Tier-2 pass.

    Returns 404 when no pass has been run yet in this session.
    """
    status = scans_api._shared_orch.get_latest_tier2_status()
    if status is None:
        raise HTTPException(status_code=404, detail="No Tier-2 pass has been run in this session")
    return {"data": status}
