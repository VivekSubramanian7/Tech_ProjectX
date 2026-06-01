"""Aggregate KPI endpoints — never exposes raw PII (FR51/NFR13)."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.api import scans as scans_api
from app.enums import ENTRIES
from app.repositories import CatalogRepository
from app.services.escalation_policy import TAU_BY_RISK

router = APIRouter(prefix="/aggregates", tags=["aggregates"])

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB = ROOT / "data" / "catalog.sqlite"
SEED_SQL = ROOT / "data" / "enum_seed.sql"

_repo = CatalogRepository(DEFAULT_DB)


@router.get("")
def get_aggregates() -> dict:
    _repo.init_db(SEED_SQL if SEED_SQL.is_file() else None)
    with _repo.connect() as conn:
        files_row = conn.execute(
            "SELECT COUNT(*) AS c, COALESCE(SUM(size), 0) AS total_bytes FROM scan_catalog"
        ).fetchone()
        findings_row = conn.execute(
            "SELECT COUNT(*) AS c FROM finding WHERE resolution_status = 'open'"
        ).fetchone()
        all_findings_row = conn.execute("SELECT COUNT(*) AS c FROM finding").fetchone()

        by_code_rows = conn.execute(
            """
            SELECT classification_code, COUNT(*) AS cnt
            FROM finding
            WHERE resolution_status = 'open'
            GROUP BY classification_code
            ORDER BY cnt DESC
            """
        ).fetchall()

        # Per-finding confidence/tier for the Tier-2 assurance picture.
        assurance_rows = conn.execute(
            """
            SELECT classification_code, confidence_score, tier
            FROM finding
            WHERE resolution_status = 'open'
            """
        ).fetchall()

    by_classification = []
    for row in by_code_rows:
        code = row["classification_code"]
        entry = ENTRIES.get(code)
        by_classification.append(
            {
                "code": code,
                "display_label": entry.display_label if entry else code,
                "count": row["cnt"],
                "risk_weight": entry.risk_weight if entry else "Unknown",
            }
        )

    # Tier-2 assurance: a finding "needs the LLM check" when its Tier-1 confidence
    # falls below the risk-tiered escalation threshold (see EscalationPolicy).
    tier2_needed = 0
    tier2_verified = 0
    for row in assurance_rows:
        if int(row["tier"]) >= 2:
            tier2_verified += 1
            continue
        entry = ENTRIES.get(row["classification_code"])
        risk_weight = entry.risk_weight if entry else "Medium"
        tau = TAU_BY_RISK.get(risk_weight, 0.85)
        if float(row["confidence_score"]) < tau:
            tier2_needed += 1

    open_count = findings_row["c"]
    assured = open_count - tier2_needed
    assurance_pct = round(100.0 * assured / open_count, 1) if open_count else 0.0

    return {
        "data": {
            "files_scanned": files_row["c"],
            "total_size_bytes": files_row["total_bytes"],
            "open_findings": open_count,
            "total_findings": all_findings_row["c"],
            "by_classification": by_classification,
            "tier2_needed": tier2_needed,
            "tier2_verified": tier2_verified,
            "assurance_pct": assurance_pct,
        }
    }


@router.post("/reset")
def reset_catalog() -> dict:
    """Clear scan catalog, findings, audit log, and in-memory scan state."""
    if scans_api._shared_orch.has_active_scan():
        raise HTTPException(status_code=409, detail="Cannot reset while a scan is in progress")

    seed = SEED_SQL if SEED_SQL.is_file() else None
    scans_api._shared_repo.init_db(seed)
    scans_api._shared_repo.reset_catalog(seed)
    scans_api._shared_orch.clear_runs()

    return {
        "data": {"reset": True},
        "meta": {"message": "Scan catalog cleared"},
    }
