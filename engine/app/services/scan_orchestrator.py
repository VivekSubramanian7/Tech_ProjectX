"""Unified scan orchestrator — text, image, delta, tier-2."""

from __future__ import annotations

import os
import sqlite3
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app import config as app_config
from app.detectors.image.ocr import OcrDetector
from app.detectors.image.pipeline import ImagePipeline
from app.detectors.image.signature import SignatureDetector
from app.detectors.image.yolo import YoloDetector
from app.detectors.router import Modality, is_scannable_path, route_file
from app.detectors.text.extract import TextSegment, extract_file, incremental_sha256, merge_detections_with_overlap
from app.detectors.text.ner import NerDetector
from app.detectors.text.regex_checksum import RegexChecksumDetector
from app.detectors.tier2.llm_text import run_tier2_text
from app.detectors.tier2.vlm_image import run_tier2_image
from app.identity import file_id as compute_file_id
from app.repositories import CatalogRepository
from app.scan_config import ScanOptions
from app.services.escalation_policy import EscalationPolicy, Tier2BudgetExceeded
from app.services.finding_write import write_detection, write_image_detection
from app.services.ownership import OwnershipResolver
from app.sources.base import FileRef, FileSource
from app.sources.local_folder import LocalFolderSource


@dataclass
class ScanRunState:
    scan_id: str
    status: str = "queued"
    files_total: int = 0
    files_scanned: int = 0
    findings_count: int = 0
    mode: str = "full"
    tier2_applied: int = 0


def _peek_magic(source: FileSource, ref: FileRef, n: int = 512) -> bytes:
    with source.open(ref) as stream:
        if hasattr(stream, "read"):
            return stream.read(n)
    return b""


def _modality_for_ref(ref: FileRef, source: FileSource) -> Modality:
    return route_file(ref.path, magic=_peek_magic(source, ref))


def _materialize_path(source: FileSource, ref: FileRef) -> Path:
    local = Path(ref.path)
    if local.is_file():
        return local
    with source.open(ref) as stream:
        data = stream.readall() if hasattr(stream, "readall") else stream.read()
    suffix = Path(ref.path).suffix or ".bin"
    fd, name = tempfile.mkstemp(suffix=suffix)
    try:
        os.write(fd, data)
    finally:
        os.close(fd)
    return Path(name)


def _is_graph_delta_source(source: FileSource) -> bool:
    return hasattr(source, "changes_since") and hasattr(source, "initial_delta_token")


def _hash_file(path: Path) -> str:
    with path.open("rb") as f:
        return incremental_sha256(f)


def _scan_text_file(
    repo: CatalogRepository,
    conn: sqlite3.Connection,
    *,
    source: FileSource,
    ref: FileRef,
    ownership: OwnershipResolver,
    options: ScanOptions,
) -> list[dict[str, Any]]:
    regex = RegexChecksumDetector()
    ner = NerDetector(use_spacy=options.use_spacy)
    written: list[dict[str, Any]] = []

    with source.open(ref) as raw:
        seg_iter, content_hash = extract_file(ref.path, raw)
        segments = list(seg_iter)

    repo.upsert_catalog(
        conn,
        file_id=ref.file_id,
        source_id=ref.scope_id,
        path=ref.path,
        content_hash=content_hash,
        size=ref.size,
        mtime=ref.mtime,
        ruleset_version=app_config.RULESET_VERSION,
        scan_status="scanning",
    )

    segment_triples: list[tuple[int, int, Any]] = []
    for seg in segments:
        for det in regex.detect(seg.text, seg.base_offset):
            segment_triples.append((det.span.start, det.span.end, det))
    ner_segments = [(s.text, s.base_offset) for s in segments]
    for det in ner.detect_batch(ner_segments):
        segment_triples.append((det.span.start, det.span.end, det))

    for det in merge_detections_with_overlap(segment_triples):
        page = _page_for_span(segments, det.span.start)
        fid = write_detection(
            repo,
            conn,
            file_id=ref.file_id,
            det=det,
            page=page,
            ownership=ownership,
            file_path=ref.path,
        )
        written.append(_canonical_text_finding(ref.file_id, det, finding_id=fid))

    repo.upsert_catalog(
        conn,
        file_id=ref.file_id,
        source_id=ref.scope_id,
        path=ref.path,
        content_hash=content_hash,
        size=ref.size,
        mtime=ref.mtime,
        ruleset_version=app_config.RULESET_VERSION,
        scan_status="complete",
    )
    return written


def _scan_image_file(
    repo: CatalogRepository,
    conn: sqlite3.Connection,
    *,
    source: FileSource,
    ref: FileRef,
    ownership: OwnershipResolver,
    options: ScanOptions,
    materialized: Path | None = None,
) -> list[dict[str, Any]]:
    path = materialized or _materialize_path(source, ref)
    content_hash = _hash_file(path)
    written: list[dict[str, Any]] = []

    repo.upsert_catalog(
        conn,
        file_id=ref.file_id,
        source_id=ref.scope_id,
        path=ref.path,
        content_hash=content_hash,
        size=ref.size,
        mtime=ref.mtime,
        ruleset_version=app_config.RULESET_VERSION,
        scan_status="scanning",
    )

    detectors = [
        YoloDetector(use_ml=options.use_ml_image),
        OcrDetector(use_ml=options.use_ml_image),
        SignatureDetector(),
    ]
    for detector in detectors:
        for det in detector.detect(path):
            fid = write_image_detection(
                repo,
                conn,
                file_id=ref.file_id,
                det=det,
                ownership=ownership,
                file_path=ref.path,
            )
            written.append(_canonical_image_finding(ref.file_id, det, finding_id=fid))

    repo.upsert_catalog(
        conn,
        file_id=ref.file_id,
        source_id=ref.scope_id,
        path=ref.path,
        content_hash=content_hash,
        size=ref.size,
        mtime=ref.mtime,
        ruleset_version=app_config.RULESET_VERSION,
        scan_status="complete",
    )
    return written


def _scan_ref(
    repo: CatalogRepository,
    conn: sqlite3.Connection,
    *,
    source: FileSource,
    ref: FileRef,
    ownership: OwnershipResolver,
    options: ScanOptions,
    materialized: Path | None = None,
) -> list[dict[str, Any]]:
    modality = _modality_for_ref(ref, source)
    if modality == Modality.TEXT:
        return _scan_text_file(repo, conn, source=source, ref=ref, ownership=ownership, options=options)
    if modality == Modality.IMAGE:
        return _scan_image_file(
            repo,
            conn,
            source=source,
            ref=ref,
            ownership=ownership,
            options=options,
            materialized=materialized,
        )
    return _scan_text_file(repo, conn, source=source, ref=ref, ownership=ownership, options=options)


def _page_for_span(segments: list[TextSegment], start: int) -> int | None:
    for seg in segments:
        if seg.base_offset <= start < seg.base_offset + len(seg.text):
            return seg.page
    return None


def _canonical_text_finding(file_id: str, det, *, finding_id: int) -> dict[str, Any]:
    from app.enums import lookup
    from app.services.scoring import final_scores

    risk, conf = final_scores(det.classification_code, det.confidence_score)
    return {
        "finding_id": finding_id,
        "file_id": file_id,
        "code": det.classification_code,
        "modality": "text",
        "span": [det.span.start, det.span.end],
        "confidence": conf,
        "risk_score": risk,
        "risk_weight": lookup(det.classification_code).risk_weight,
        "masked": det.masked_snippet,
    }


def _canonical_image_finding(file_id: str, det, *, finding_id: int) -> dict[str, Any]:
    from app.enums import lookup
    from app.services.scoring import final_scores

    risk, conf = final_scores(det.classification_code, det.confidence_score)
    b = det.bbox
    return {
        "finding_id": finding_id,
        "file_id": file_id,
        "code": det.classification_code,
        "modality": "image",
        "bbox": [b.x, b.y, b.w, b.h],
        "confidence": conf,
        "risk_score": risk,
        "risk_weight": lookup(det.classification_code).risk_weight,
        "masked": det.masked_snippet,
    }


def _content_hash_for_ref(ref: FileRef, source: FileSource) -> str:
    modality = _modality_for_ref(ref, source)
    if modality == Modality.TEXT or modality == Modality.OCR:
        with source.open(ref) as raw:
            _, content_hash = extract_file(ref.path, raw)
        return content_hash
    return _hash_file(_materialize_path(source, ref))


def _should_process(
    existing: sqlite3.Row | None,
    ref: FileRef,
    *,
    reapply_ruleset: bool,
    content_hash: str | None = None,
) -> bool:
    if existing is None:
        return True
    if reapply_ruleset and existing["ruleset_version"] != app_config.RULESET_VERSION:
        return True
    if existing["size"] != ref.size or existing["mtime"] != ref.mtime:
        if content_hash is not None and existing["content_hash"] == content_hash:
            return False
        return True
    return False


def _scannable_refs(source: FileSource) -> list[FileRef]:
    return [ref for ref in source.iter_files() if is_scannable_path(ref.path)]


class ScanOrchestrator:
    def __init__(
        self,
        repo: CatalogRepository,
        *,
        ownership_map_path: Path | None = None,
        default_options: ScanOptions | None = None,
    ) -> None:
        self.repo = repo
        self.ownership = OwnershipResolver.from_json_file(
            ownership_map_path or Path(__file__).resolve().parents[3] / "data" / "mock_owners.json"
        )
        self.default_options = default_options or ScanOptions()
        self._runs: dict[str, ScanRunState] = {}

    def run_scan(
        self,
        target: Path | FileSource,
        *,
        scope_id: str | None = None,
        mode: str = "full",
        reapply_ruleset: bool = False,
        tier2: bool = False,
        options: ScanOptions | None = None,
        scan_id: str | None = None,
    ) -> dict[str, Any]:
        """Unified entry: full or delta scan over local folder or any FileSource."""
        scan_options = options or self.default_options
        source = (
            target
            if isinstance(target, FileSource)
            else LocalFolderSource(target, scope_id=scope_id)
        )
        scope = scope_id or getattr(source, "_drive_id", None) or getattr(source, "_scope_id", None)
        if scope is None and isinstance(target, Path):
            scope = str(target.resolve())

        if mode == "delta" and _is_graph_delta_source(source):
            result = self._run_graph_delta_source(
                source,
                scope_id=scope or "",
                reapply_ruleset=reapply_ruleset,
                options=scan_options,
                scan_id=scan_id,
            )
        elif mode == "delta":
            result = self._run_delta_source(
                source,
                scope_id=scope or "",
                reapply_ruleset=reapply_ruleset,
                options=scan_options,
                scan_id=scan_id,
            )
        else:
            result = self._run_full_source(source, options=scan_options, scan_id=scan_id)

        if tier2:
            tier2_stats = self._apply_tier2(result["findings"])
            result.update(tier2_stats)

        return result

    def start_scan(
        self,
        target: Path | FileSource,
        *,
        scope_id: str | None = None,
        mode: str = "full",
        reapply_ruleset: bool = False,
        tier2: bool = False,
        options: ScanOptions | None = None,
    ) -> str:
        scan_id = str(uuid.uuid4())
        scan_options = options or self.default_options
        source = (
            target
            if isinstance(target, FileSource)
            else LocalFolderSource(target, scope_id=scope_id)
        )
        refs = _scannable_refs(source)
        state = ScanRunState(scan_id=scan_id, status="scanning", files_total=len(refs), mode=mode)
        self._runs[scan_id] = state

        with self.repo.connect() as conn:
            self.repo.insert_scan_run(
                conn,
                scan_id=scan_id,
                scope_id=scope_id,
                mode=mode,
                status="scanning",
                files_total=len(refs),
                ruleset_version=app_config.RULESET_VERSION,
            )
            conn.commit()

        result = self.run_scan(
            target,
            scope_id=scope_id,
            mode=mode,
            reapply_ruleset=reapply_ruleset,
            tier2=tier2,
            options=scan_options,
            scan_id=scan_id,
        )
        state.files_scanned = result.get("files_scanned") or result.get("files_processed", 0) + result.get(
            "files_skipped", 0
        )
        state.findings_count = len(result["findings"])
        state.tier2_applied = result.get("tier2_applied", 0)
        state.status = "complete"

        with self.repo.connect() as conn:
            self.repo.update_scan_run(
                conn,
                scan_id,
                status="complete",
                files_scanned=state.files_scanned,
                findings_count=state.findings_count,
                tier2_applied=state.tier2_applied,
            )
            conn.commit()

        return scan_id

    def start_full(self, folder: Path, *, scope_id: str | None = None) -> str:
        """Backward-compatible alias for full local scan."""
        return self.start_scan(folder, scope_id=scope_id, mode="full")

    def get_scan_status(self, scan_id: str) -> dict[str, Any]:
        state = self._runs.get(scan_id)
        if state is not None:
            return self._status_dict(state)

        with self.repo.connect() as conn:
            row = self.repo.get_scan_run(conn, scan_id)
        if row is None:
            raise KeyError(scan_id)
        return {
            "scan_id": row["scan_id"],
            "status": row["status"],
            "files_total": row["files_total"],
            "files_scanned": row["files_scanned"],
            "findings_count": row["findings_count"],
            "tier2_applied": row["tier2_applied"],
            "mode": row["mode"],
        }

    @staticmethod
    def _status_dict(state: ScanRunState) -> dict[str, Any]:
        return {
            "scan_id": state.scan_id,
            "status": state.status,
            "files_total": state.files_total,
            "files_scanned": state.files_scanned,
            "findings_count": state.findings_count,
            "tier2_applied": state.tier2_applied,
            "mode": state.mode,
        }

    def run_full(self, folder: Path, *, scope_id: str | None = None) -> dict[str, Any]:
        return self.run_scan(folder, scope_id=scope_id, mode="full")

    def run_delta(
        self,
        folder: Path,
        *,
        scope_id: str | None = None,
        reapply_ruleset: bool = False,
    ) -> dict[str, Any]:
        return self.run_scan(
            folder,
            scope_id=scope_id,
            mode="delta",
            reapply_ruleset=reapply_ruleset,
        )

    def run_full_with_escalation(
        self,
        folder: Path,
        *,
        scope_id: str | None = None,
        tier2_enabled: bool = False,
    ) -> dict[str, Any]:
        result = self.run_scan(folder, scope_id=scope_id, mode="full", tier2=tier2_enabled)
        return {
            **result,
            "tier1_complete": True,
            "tier2_pending": result.get("tier2_applied", 0),
            "tier2_errors": result.get("tier2_errors", 0),
        }

    def _tick_progress(
        self,
        scan_id: str | None,
        files_scanned: int,
        findings_count: int,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        if scan_id is None:
            return
        state = self._runs.get(scan_id)
        if state is not None:
            state.files_scanned = files_scanned
            state.findings_count = findings_count
        if conn is not None:
            conn.execute(
                """
                UPDATE scan_run
                SET files_scanned = ?, findings_count = ?, status = 'scanning'
                WHERE scan_id = ?
                """,
                (files_scanned, findings_count, scan_id),
            )
            return
        with self.repo.connect() as tick_conn:
            tick_conn.execute(
                """
                UPDATE scan_run
                SET files_scanned = ?, findings_count = ?, status = 'scanning'
                WHERE scan_id = ?
                """,
                (files_scanned, findings_count, scan_id),
            )
            tick_conn.commit()

    def _run_full_source(
        self,
        source: FileSource,
        *,
        options: ScanOptions,
        scan_id: str | None = None,
    ) -> dict[str, Any]:
        refs = _scannable_refs(source)
        text_refs = [r for r in refs if _modality_for_ref(r, source) != Modality.IMAGE]
        image_refs = [r for r in refs if _modality_for_ref(r, source) == Modality.IMAGE]
        all_findings: list[dict[str, Any]] = []
        scanned = 0

        with self.repo.connect() as conn:
            for ref in text_refs:
                all_findings.extend(
                    _scan_ref(
                        self.repo,
                        conn,
                        source=source,
                        ref=ref,
                        ownership=self.ownership,
                        options=options,
                    )
                )
                scanned += 1
                self._tick_progress(scan_id, scanned, len(all_findings), conn)

            if image_refs:
                paths = [_materialize_path(source, r) for r in image_refs]
                ImagePipeline().run(paths)
                for ref, path in zip(image_refs, paths, strict=True):
                    all_findings.extend(
                        _scan_ref(
                            self.repo,
                            conn,
                            source=source,
                            ref=ref,
                            ownership=self.ownership,
                            options=options,
                            materialized=path,
                        )
                    )
                    scanned += 1
                    self._tick_progress(scan_id, scanned, len(all_findings), conn)

            if _is_graph_delta_source(source):
                scope = getattr(source, "_drive_id", None)
                if scope:
                    self.repo.set_delta_token(conn, scope, source.initial_delta_token())

            conn.commit()

        return {
            "ruleset_version": app_config.RULESET_VERSION,
            "files_scanned": len(refs),
            "findings": _sort_findings(all_findings),
        }

    def _run_delta_source(
        self,
        source: FileSource,
        *,
        scope_id: str,
        reapply_ruleset: bool,
        options: ScanOptions,
        scan_id: str | None = None,
    ) -> dict[str, Any]:
        all_findings: list[dict[str, Any]] = []
        files_processed = 0
        files_skipped = 0
        scanned = 0

        with self.repo.connect() as conn:
            seen_ids: set[str] = set()
            refs = _scannable_refs(source)
            for ref in refs:
                seen_ids.add(ref.file_id)
                existing = self.repo.get_catalog_entry(conn, ref.file_id)
                content_hash: str | None = None
                if existing is not None and (
                    existing["size"] != ref.size or existing["mtime"] != ref.mtime
                ):
                    content_hash = _content_hash_for_ref(ref, source)
                if not _should_process(
                    existing, ref, reapply_ruleset=reapply_ruleset, content_hash=content_hash
                ):
                    files_skipped += 1
                    scanned += 1
                    self._tick_progress(scan_id, scanned, len(all_findings), conn)
                    continue
                if existing is not None:
                    conn.execute("DELETE FROM finding WHERE file_id = ?", (ref.file_id,))
                all_findings.extend(
                    _scan_ref(
                        self.repo,
                        conn,
                        source=source,
                        ref=ref,
                        ownership=self.ownership,
                        options=options,
                    )
                )
                files_processed += 1
                scanned += 1
                self._tick_progress(scan_id, scanned, len(all_findings), conn)

            for row in self.repo.list_catalog_for_scope(conn, scope_id):
                if row["file_id"] not in seen_ids:
                    self.repo.delete_catalog(conn, row["file_id"])

            conn.commit()

        return {
            "ruleset_version": app_config.RULESET_VERSION,
            "files_processed": files_processed,
            "files_skipped": files_skipped,
            "findings": _sort_findings(all_findings),
        }

    def _run_graph_delta_source(
        self,
        source: FileSource,
        *,
        scope_id: str,
        reapply_ruleset: bool,
        options: ScanOptions,
        scan_id: str | None = None,
    ) -> dict[str, Any]:
        all_findings: list[dict[str, Any]] = []
        files_processed = 0
        files_skipped = 0

        with self.repo.connect() as conn:
            token = self.repo.get_delta_token(conn, scope_id) or source.initial_delta_token()
            changes, new_token = source.changes_since(token)
            scanned = 0
            total = len(changes)

            for change in changes:
                change_type = change.get("change_type")
                item_id = change["item_id"]
                if change_type == "deleted":
                    fid = compute_file_id("onedrive", scope_id, item_id)
                    self.repo.delete_catalog(conn, fid)
                    scanned += 1
                    self._tick_progress(scan_id, scanned, len(all_findings), conn)
                    continue

                ref = source.ref_for_item(item_id) if hasattr(source, "ref_for_item") else None
                if ref is None or not is_scannable_path(ref.path):
                    files_skipped += 1
                    scanned += 1
                    self._tick_progress(scan_id, scanned, len(all_findings), conn)
                    continue

                existing = self.repo.get_catalog_entry(conn, ref.file_id)
                content_hash = _content_hash_for_ref(ref, source)
                if change_type != "created" and not _should_process(
                    existing,
                    ref,
                    reapply_ruleset=reapply_ruleset,
                    content_hash=content_hash,
                ):
                    files_skipped += 1
                    scanned += 1
                    self._tick_progress(scan_id, scanned, len(all_findings), conn)
                    continue

                if existing is not None:
                    conn.execute("DELETE FROM finding WHERE file_id = ?", (ref.file_id,))
                all_findings.extend(
                    _scan_ref(
                        self.repo,
                        conn,
                        source=source,
                        ref=ref,
                        ownership=self.ownership,
                        options=options,
                    )
                )
                files_processed += 1
                scanned += 1
                self._tick_progress(scan_id, scanned, len(all_findings), conn)

            self.repo.set_delta_token(conn, scope_id, new_token)
            conn.commit()

        return {
            "ruleset_version": app_config.RULESET_VERSION,
            "files_processed": files_processed,
            "files_skipped": files_skipped,
            "findings": _sort_findings(all_findings),
            "delta_changes": total,
        }

    def _apply_tier2(self, findings: list[dict[str, Any]]) -> dict[str, Any]:
        policy = EscalationPolicy()
        applied = 0
        errors = 0
        with self.repo.connect() as conn:
            for finding in findings:
                try:
                    if not policy.should_escalate(finding["risk_weight"], finding["confidence"]):
                        continue
                    policy.record_escalation()
                    try:
                        if finding.get("modality") == "image":
                            verdict = run_tier2_image(
                                {
                                    "classification_code": finding["code"],
                                    "confidence_score": finding["confidence"],
                                },
                                ephemeral_crop=b"",
                            )
                        else:
                            verdict = run_tier2_text(
                                {
                                    "classification_code": finding["code"],
                                    "confidence_score": finding["confidence"],
                                    "risk_weight": finding["risk_weight"],
                                    "masked_snippet": finding["masked"],
                                },
                                ephemeral_snippet=finding["masked"],
                            )
                        self.repo.update_finding_tier2(
                            conn,
                            finding["finding_id"],
                            confidence_score=verdict.confidence_score,
                            tier=2,
                            model_version=verdict.model_version,
                            prompt_hash=verdict.prompt_hash,
                        )
                        applied += 1
                    except Exception:
                        errors += 1
                except Tier2BudgetExceeded:
                    break
            conn.commit()
        return {"tier2_applied": applied, "tier2_errors": errors}

    def tier1_scan_callable(self, folder: Path, *, scope_id: str | None = None):
        def _run():
            findings = self.run_full(folder, scope_id=scope_id)["findings"]
            return [{k: v for k, v in f.items() if k != "finding_id"} for f in findings]

        return _run


def _sort_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        findings,
        key=lambda f: (f["file_id"], f.get("span", f.get("bbox", [0]))[0], f["code"]),
    )
