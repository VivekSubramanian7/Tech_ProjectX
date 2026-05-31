"""Persist detections as privacy-safe findings."""

from __future__ import annotations

import sqlite3

from app.audit import audit_finding_created
from app.detectors.base import Detection, ImageDetection
from app.repositories import CatalogRepository
from app.services.ownership import OwnershipResolver
from app.services.scoring import final_scores


def location_from_detection(det: Detection, page: int | None = None) -> dict:
    loc: dict = {
        "modality": "text",
        "span": [det.span.start, det.span.end],
    }
    if page is not None:
        loc["page"] = page
    return loc


def location_from_image(det: ImageDetection) -> dict:
    b = det.bbox
    return {
        "modality": "image",
        "bbox": [b.x, b.y, b.w, b.h],
    }


def write_detection(
    repo: CatalogRepository,
    conn: sqlite3.Connection,
    *,
    file_id: str,
    det: Detection,
    page: int | None,
    ownership: OwnershipResolver,
    file_path: str,
) -> int:
    risk, confidence = final_scores(det.classification_code, det.confidence_score)
    own = ownership.resolve(file_path)
    fid = repo.insert_finding(
        conn,
        file_id=file_id,
        classification_code=det.classification_code,
        location=location_from_detection(det, page),
        masked_snippet=det.masked_snippet,
        risk_score=risk,
        confidence_score=confidence,
        detector_version=det.detector_version,
        model_version=det.model_version,
        prompt_hash=None,
        owner_user_id=own.owner_user_id,
        resolution_method=own.resolution_method,
    )
    audit_finding_created(
        repo,
        conn,
        finding_id=fid,
        detector_version=det.detector_version,
        model_version=det.model_version,
    )
    if own.unresolved:
        repo.append_audit(
            conn,
            entity_type="file",
            entity_id=file_id,
            action="owner_unresolved",
            justification=file_path,
        )
    return fid


def write_image_detection(
    repo: CatalogRepository,
    conn: sqlite3.Connection,
    *,
    file_id: str,
    det: ImageDetection,
    ownership: OwnershipResolver,
    file_path: str,
) -> int:
    risk, confidence = final_scores(det.classification_code, det.confidence_score)
    own = ownership.resolve(file_path)
    fid = repo.insert_finding(
        conn,
        file_id=file_id,
        classification_code=det.classification_code,
        location=location_from_image(det),
        masked_snippet=det.masked_snippet,
        risk_score=risk,
        confidence_score=confidence,
        detector_version=det.detector_version,
        model_version=det.model_version,
        prompt_hash=None,
        owner_user_id=own.owner_user_id,
        resolution_method=own.resolution_method,
    )
    audit_finding_created(
        repo,
        conn,
        finding_id=fid,
        detector_version=det.detector_version,
        model_version=det.model_version,
    )
    if own.unresolved:
        repo.append_audit(
            conn,
            entity_type="file",
            entity_id=file_id,
            action="owner_unresolved",
            justification=file_path,
        )
    return fid
