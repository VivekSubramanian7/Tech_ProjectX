"""Owner-facing findings endpoints — never exposes raw PII."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app.enums import ENTRIES
from app.repositories import CatalogRepository
from app.services.file_content import load_owner_file_preview

router = APIRouter(tags=["findings"])

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB = ROOT / "data" / "catalog.sqlite"
SEED_SQL = ROOT / "data" / "enum_seed.sql"
DEMO_OWNER_ID = "user-alpha"

_repo = CatalogRepository(DEFAULT_DB)

CONSEQUENCE_HINTS: dict[str, str] = {
    "PASSPORT_NUMBER": "Passport numbers are highly sensitive — keeping them without a clear business reason creates legal exposure.",
    "DE_PERSONALAUSWEIS": "National ID numbers need strict justification and protection under GDPR.",
    "CREDIT_CARD_NUMBER": "Payment card data should not be stored unless strictly necessary and secured.",
    "DE_SOZIALVERSICHERUNGSNR": "Social security numbers are critical identifiers — limit retention and access.",
    "FACE": "Photos of people may be biometric data — confirm you still need this file.",
    "LICENSE_PLATE": "Vehicle licence plates can identify a person — keep only with a clear reason.",
    "SIGNATURE": "Signatures can identify a person — only keep if there is a documented business need.",
    "HOME_ADDRESS": "Home addresses are personal data — check whether a work address would suffice.",
    "IBAN": "Bank account details need a documented reason to keep and must be protected.",
    "EMAIL": "Email addresses can identify someone — confirm this file is still needed for work.",
    "PHONE_NUMBER": "Phone numbers are personal data — delete or justify retention.",
    "PERSON_NAME": "Names combined with other details can identify someone — confirm the file is necessary.",
}

DEFAULT_CONSEQUENCE = (
    "This looks like personal data. If you no longer need it for work, deleting reduces GDPR risk for Bosch."
)

CONFIDENCE_LIKELY_THRESHOLD = 0.75


class ActionBody(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


def _acting_user(x_acting_user: str | None) -> str:
    return x_acting_user or DEMO_OWNER_ID


def _confidence_label(score: float) -> str:
    return "Likely" if score >= CONFIDENCE_LIKELY_THRESHOLD else "Not sure"


def _serialize_finding(row: Any) -> dict[str, Any]:
    code = row["classification_code"]
    entry = ENTRIES.get(code)
    location = json.loads(row["location_json"])
    return {
        "id": row["id"],
        "file_id": row["file_id"],
        "file_path": row["file_path"],
        "classification_code": code,
        "display_label": entry.display_label if entry else code,
        "risk_weight": entry.risk_weight if entry else "Medium",
        "consequence_hint": CONSEQUENCE_HINTS.get(code, DEFAULT_CONSEQUENCE),
        "masked_snippet": row["masked_snippet"],
        "confidence_label": _confidence_label(float(row["confidence_score"])),
        "location": location,
        "resolution_status": row["resolution_status"],
    }


def _ensure_owner(row: Any, owner_user_id: str) -> None:
    if row["owner_user_id"] != owner_user_id:
        raise HTTPException(status_code=403, detail="Finding not owned by this user")
    if row["resolution_status"] != "open":
        raise HTTPException(status_code=409, detail="Finding is no longer open")


@router.get("/me/files/{file_id}/content")
def get_my_file_content(
    file_id: str,
    x_acting_user: str | None = Header(default=None),
) -> dict:
    owner_user_id = _acting_user(x_acting_user)
    _repo.init_db(SEED_SQL if SEED_SQL.is_file() else None)
    with _repo.connect() as conn:
        try:
            preview = load_owner_file_preview(
                _repo, conn, file_id=file_id, owner_user_id=owner_user_id
            )
        except PermissionError:
            raise HTTPException(status_code=403, detail="File not owned by this user") from None
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="File not found") from None
        _repo.append_audit(
            conn,
            entity_type="file",
            entity_id=file_id,
            action="document_view",
            actor=owner_user_id,
        )
        conn.commit()
    return {"data": preview}


@router.get("/me/findings")
def list_my_findings(x_acting_user: str | None = Header(default=None)) -> dict:
    owner_user_id = _acting_user(x_acting_user)
    _repo.init_db(SEED_SQL if SEED_SQL.is_file() else None)
    with _repo.connect() as conn:
        rows = _repo.list_open_findings_for_owner(conn, owner_user_id)
    return {
        "data": [_serialize_finding(r) for r in rows],
        "meta": {"owner_user_id": owner_user_id, "open_count": len(rows)},
    }


@router.post("/findings/{finding_id}/keep")
def keep_finding(
    finding_id: int,
    body: ActionBody,
    x_acting_user: str | None = Header(default=None),
) -> dict:
    owner_user_id = _acting_user(x_acting_user)
    _repo.init_db(SEED_SQL if SEED_SQL.is_file() else None)
    with _repo.connect() as conn:
        row = _repo.get_finding(conn, finding_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Finding not found")
        _ensure_owner(row, owner_user_id)
        updated = _repo.update_finding_resolution(
            conn,
            finding_id,
            resolution_status="kept",
            actor=owner_user_id,
            action="keep",
            justification=body.reason,
        )
        conn.commit()
    return {"data": _serialize_finding(updated)}


@router.post("/findings/{finding_id}/delete")
def delete_finding(
    finding_id: int,
    x_acting_user: str | None = Header(default=None),
) -> dict:
    owner_user_id = _acting_user(x_acting_user)
    _repo.init_db(SEED_SQL if SEED_SQL.is_file() else None)
    with _repo.connect() as conn:
        row = _repo.get_finding(conn, finding_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Finding not found")
        _ensure_owner(row, owner_user_id)
        updated = _repo.update_finding_resolution(
            conn,
            finding_id,
            resolution_status="deleted_pending",
            actor=owner_user_id,
            action="soft_delete",
        )
        conn.commit()
    return {"data": _serialize_finding(updated)}


@router.post("/findings/{finding_id}/restore")
def restore_finding(
    finding_id: int,
    x_acting_user: str | None = Header(default=None),
) -> dict:
    owner_user_id = _acting_user(x_acting_user)
    _repo.init_db(SEED_SQL if SEED_SQL.is_file() else None)
    with _repo.connect() as conn:
        row = _repo.get_finding(conn, finding_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Finding not found")
        if row["owner_user_id"] != owner_user_id:
            raise HTTPException(status_code=403, detail="Finding not owned by this user")
        if row["resolution_status"] != "deleted_pending":
            raise HTTPException(status_code=409, detail="Finding is not pending deletion")
        updated = _repo.update_finding_resolution(
            conn,
            finding_id,
            resolution_status="open",
            actor=owner_user_id,
            action="restore",
        )
        conn.commit()
    return {"data": _serialize_finding(updated)}


@router.post("/findings/{finding_id}/escalate")
def escalate_finding(
    finding_id: int,
    body: ActionBody,
    x_acting_user: str | None = Header(default=None),
) -> dict:
    owner_user_id = _acting_user(x_acting_user)
    _repo.init_db(SEED_SQL if SEED_SQL.is_file() else None)
    with _repo.connect() as conn:
        row = _repo.get_finding(conn, finding_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Finding not found")
        _ensure_owner(row, owner_user_id)
        updated = _repo.update_finding_resolution(
            conn,
            finding_id,
            resolution_status="escalated",
            actor=owner_user_id,
            action="escalate",
            justification=body.reason,
        )
        conn.commit()
    return {"data": _serialize_finding(updated)}


@router.post("/findings/{finding_id}/false-positive")
def flag_false_positive(
    finding_id: int,
    x_acting_user: str | None = Header(default=None),
) -> dict:
    owner_user_id = _acting_user(x_acting_user)
    _repo.init_db(SEED_SQL if SEED_SQL.is_file() else None)
    with _repo.connect() as conn:
        row = _repo.get_finding(conn, finding_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Finding not found")
        _ensure_owner(row, owner_user_id)
        updated = _repo.update_finding_resolution(
            conn,
            finding_id,
            resolution_status="false_positive",
            actor=owner_user_id,
            action="false_positive",
        )
        conn.commit()
    return {"data": _serialize_finding(updated)}
