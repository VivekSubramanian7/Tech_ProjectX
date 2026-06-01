"""Unified scan orchestrator — text, image, delta, tier-2."""

from __future__ import annotations

import io
import json
import logging
import os
import sqlite3
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app import config as app_config
from app.detectors.image.ml_status import probe_ml_image_status
from app.detectors.image.ocr import OcrDetector
from app.detectors.image.signature import SignatureDetector
from app.detectors.image.warmup import warm_image_models
from app.detectors.image.yolo import YoloDetector
from app.detectors.router import Modality, is_scannable_path, route_file
from app.detectors.text.extract import TextSegment, extract_file, incremental_sha256, merge_detections_with_overlap
from app.detectors.text.ner import NerDetector
from app.detectors.text.regex_checksum import RegexChecksumDetector
from app.detectors.tier2.llm_text import run_tier2_text
from app.detectors.tier2.vlm_image import run_tier2_image
from app.identity import file_id as compute_file_id
from app.repositories import CatalogRepository
from app.scan_config import ScanOptions, resolve_worker_count
from app.services.escalation_policy import EscalationPolicy, Tier2BudgetExceeded
from app.services.finding_write import write_detection, write_image_detection
from app.services.ownership import OwnershipResolver
from app.sources.base import FileRef, FileSource
from app.sources.local_folder import LocalFolderSource

logger = logging.getLogger(__name__)

# Emit classify-phase status every N files so large estates don't look frozen at 0%.
_CLASSIFY_PROGRESS_BATCH = 250
# Back off when another connection (e.g. a concurrent init_db) holds the write lock.
_PROGRESS_LOCK_RETRIES = 6


@dataclass
class ScanRunState:
    scan_id: str
    status: str = "queued"
    files_total: int = 0
    files_scanned: int = 0
    findings_count: int = 0
    mode: str = "full"
    tier2_applied: int = 0
    current_file: str | None = None
    phase: str | None = None


@dataclass
class Tier2JobState:
    job_id: str
    status: str = "running"
    processed: int = 0
    confirmed: int = 0
    rejected: int = 0
    errors: int = 0


def _peek_magic(source: FileSource, ref: FileRef, n: int = 512) -> bytes:
    with source.open(ref) as stream:
        if hasattr(stream, "read"):
            return stream.read(n)
    return b""


def _modality_for_ref(ref: FileRef, source: FileSource) -> Modality:
    """Extension-based routing; magic peek only for PDF (text vs OCR)."""
    if Path(ref.path).suffix.lower() == ".pdf":
        return route_file(ref.path, magic=_peek_magic(source, ref))
    return route_file(ref.path)


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
        native_id=ref.native_id,
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
        native_id=ref.native_id,
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
    from app.detectors.image._png import decode_bytes

    path = materialized or _materialize_path(source, ref)
    # Read the bytes once; reuse for hashing, hint chunks, and a single decode.
    data = path.read_bytes()
    content_hash = incremental_sha256(io.BytesIO(data))
    decoded = None
    try:
        decoded = decode_bytes(data, path)
    except ValueError:
        decoded = None  # unsupported format → detectors fall back to hint/raw bytes
    written: list[dict[str, Any]] = []

    logger.info("Image scan started: %s", ref.path)

    repo.upsert_catalog(
        conn,
        file_id=ref.file_id,
        source_id=ref.scope_id,
        path=ref.path,
        native_id=ref.native_id,
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
        for det in detector.detect(path, decoded=decoded, data=data):
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
        native_id=ref.native_id,
        content_hash=content_hash,
        size=ref.size,
        mtime=ref.mtime,
        ruleset_version=app_config.RULESET_VERSION,
        scan_status="complete",
    )
    logger.info("Image scan complete: %s (%d findings)", ref.path, len(written))
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
    modality: Modality | None = None,
) -> list[dict[str, Any]]:
    if modality is None:
        modality = _modality_for_ref(ref, source)
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


def _scan_ref_safe(
    repo: CatalogRepository,
    conn: sqlite3.Connection,
    *,
    source: FileSource,
    ref: FileRef,
    ownership: OwnershipResolver,
    options: ScanOptions,
    modality: Modality | None = None,
) -> list[dict[str, Any]]:
    """Scan one file, isolating failures so a single bad file never aborts the scan."""
    try:
        return _scan_ref(
            repo,
            conn,
            source=source,
            ref=ref,
            ownership=ownership,
            options=options,
            modality=modality,
        )
    except Exception:
        logger.exception("Skipping unreadable/failed file: %s", ref.path)
        return []


class _DetectorPool:
    """Thread-local detector instances for the parallel full-scan path.

    Each worker thread builds (and reuses) its own detectors. This matters for
    the stateful ones — spaCy ``Language`` and any per-instance buffers are not
    safe to call concurrently across threads — and keeps the cheap regex/rule
    detectors off the per-file allocation path.
    """

    def __init__(self, options: ScanOptions) -> None:
        self._options = options
        self._local = threading.local()

    def text(self) -> tuple[RegexChecksumDetector, NerDetector]:
        if not hasattr(self._local, "regex"):
            self._local.regex = RegexChecksumDetector()
            self._local.ner = NerDetector(use_spacy=self._options.use_spacy)
        return self._local.regex, self._local.ner

    def image(self) -> tuple[YoloDetector, OcrDetector, SignatureDetector]:
        if not hasattr(self._local, "yolo"):
            self._local.yolo = YoloDetector(use_ml=self._options.use_ml_image)
            self._local.ocr = OcrDetector(use_ml=self._options.use_ml_image)
            self._local.sig = SignatureDetector()
        return self._local.yolo, self._local.ocr, self._local.sig


# Detection result for one file: (kind, content_hash, payload). For text the
# payload is a list of (Detection, page); for image a list of ImageDetection.
_DetectResult = tuple[str, str, list[Any]]


def _detect_text_file(
    source: FileSource, ref: FileRef, options: ScanOptions, pool: _DetectorPool
) -> _DetectResult:
    """Pure detection for a text file — no DB, no shared mutable state."""
    regex, ner = pool.text()
    with source.open(ref) as raw:
        seg_iter, content_hash = extract_file(ref.path, raw)
        segments = list(seg_iter)

    segment_triples: list[tuple[int, int, Any]] = []
    for seg in segments:
        for det in regex.detect(seg.text, seg.base_offset):
            segment_triples.append((det.span.start, det.span.end, det))
    ner_segments = [(s.text, s.base_offset) for s in segments]
    for det in ner.detect_batch(ner_segments):
        segment_triples.append((det.span.start, det.span.end, det))

    dets: list[Any] = []
    for det in merge_detections_with_overlap(segment_triples):
        page = _page_for_span(segments, det.span.start)
        dets.append((det, page))
    return ("text", content_hash, dets)


def _detect_image_file(
    source: FileSource,
    ref: FileRef,
    options: ScanOptions,
    pool: _DetectorPool,
    *,
    materialized: Path | None = None,
) -> _DetectResult:
    """Pure detection for an image file — no DB. OCR always runs (never skipped)."""
    from app.detectors.image._png import decode_bytes

    path = materialized or _materialize_path(source, ref)
    data = path.read_bytes()
    content_hash = incremental_sha256(io.BytesIO(data))
    decoded = None
    try:
        decoded = decode_bytes(data, path)
    except ValueError:
        decoded = None  # unsupported format → detectors fall back to hint/raw bytes

    yolo, ocr, sig = pool.image()
    dets: list[Any] = []
    for detector in (yolo, ocr, sig):
        for det in detector.detect(path, decoded=decoded, data=data):
            dets.append(det)
    return ("image", content_hash, dets)


def _detect_ref_safe(
    source: FileSource,
    ref: FileRef,
    modality: Modality,
    options: ScanOptions,
    pool: _DetectorPool,
) -> _DetectResult | None:
    """Detect one file, isolating failures (one bad file never aborts the scan)."""
    try:
        if modality == Modality.IMAGE:
            return _detect_image_file(source, ref, options, pool)
        return _detect_text_file(source, ref, options, pool)
    except Exception:
        logger.exception("Skipping unreadable/failed file: %s", ref.path)
        return None


def _write_ref_result(
    repo: CatalogRepository,
    conn: sqlite3.Connection,
    ref: FileRef,
    result: _DetectResult | None,
    ownership: OwnershipResolver,
) -> list[dict[str, Any]]:
    """Persist a file's detections on the main thread (single catalog upsert).

    Writing happens in a fixed ref order across the scan so the autoincrement
    finding ids — and therefore the catalog — are byte-identical run to run.
    """
    if result is None:
        return []
    kind, content_hash, dets = result
    # Single terminal upsert (was previously written twice: scanning→complete).
    repo.upsert_catalog(
        conn,
        file_id=ref.file_id,
        source_id=ref.scope_id,
        path=ref.path,
        native_id=ref.native_id,
        content_hash=content_hash,
        size=ref.size,
        mtime=ref.mtime,
        ruleset_version=app_config.RULESET_VERSION,
        scan_status="complete",
    )
    written: list[dict[str, Any]] = []
    if kind == "image":
        for det in dets:
            fid = write_image_detection(
                repo, conn, file_id=ref.file_id, det=det, ownership=ownership, file_path=ref.path
            )
            written.append(_canonical_image_finding(ref.file_id, det, finding_id=fid))
    else:
        for det, page in dets:
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
    return written


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


def _file_category(path: str) -> str:
    """Normalized file-type key for Tier-1 throughput breakdown (by extension)."""
    ext = Path(path).suffix.lower().lstrip(".")
    if ext == "jpeg":
        return "jpg"
    if ext == "tif":
        return "tiff"
    return ext or "other"


class _PerfAccumulator:
    """Accumulates Tier-1 scan throughput: bytes + per-file-type counts/bytes."""

    def __init__(self) -> None:
        self.total_bytes = 0
        self.by_type: dict[str, dict[str, int]] = {}

    def add(self, ref: FileRef) -> None:
        size = int(ref.size or 0)
        self.total_bytes += size
        bucket = self.by_type.setdefault(_file_category(ref.path), {"files": 0, "bytes": 0})
        bucket["files"] += 1
        bucket["bytes"] += size

    def as_dict(self) -> dict[str, Any]:
        return {"total_bytes": self.total_bytes, "by_type": self.by_type}


def _perf_fields(result: dict[str, Any]) -> tuple[int | None, str | None]:
    """Extract (total_bytes, type_breakdown_json) from a scan result, if present."""
    perf = result.get("perf") or {}
    by_type = perf.get("by_type")
    total_bytes = perf.get("total_bytes")
    return total_bytes, (json.dumps(by_type) if by_type is not None else None)


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
        self._tier2_runs: dict[str, Tier2JobState] = {}
        self._active_tier2_job_id: str | None = None

    def has_active_scan(self) -> bool:
        return any(state.status == "scanning" for state in self._runs.values())

    def clear_runs(self) -> None:
        self._runs.clear()
        self._tier2_runs.clear()
        self._active_tier2_job_id = None

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
        refs: list[FileRef] | None = None,
    ) -> dict[str, Any]:
        """Unified entry: full or delta scan over local folder or any FileSource."""
        scan_options = options or self.default_options
        # NOTE: probing the image ML stack costs ~1.8s, so it is deferred to the
        # image branch of _run_full_source (only when image files are present)
        # rather than run unconditionally on every (often text-only) scan.
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
            result = self._run_full_source(
                source, options=scan_options, scan_id=scan_id, refs=refs
            )

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

        started = time.perf_counter()
        result = self.run_scan(
            target,
            scope_id=scope_id,
            mode=mode,
            reapply_ruleset=reapply_ruleset,
            tier2=tier2,
            options=scan_options,
            scan_id=scan_id,
            refs=refs,
        )
        duration_ms = int((time.perf_counter() - started) * 1000)
        total_bytes, type_breakdown = _perf_fields(result)
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
                total_bytes=total_bytes,
                duration_ms=duration_ms,
                type_breakdown=type_breakdown,
            )
            conn.commit()

        return scan_id

    def begin_scan(
        self,
        target: Path | FileSource,
        *,
        scope_id: str | None = None,
        mode: str = "full",
        reapply_ruleset: bool = False,
        tier2: bool = False,
        options: ScanOptions | None = None,
    ) -> str:
        """Start a scan in a background thread and return the scan_id immediately."""
        import uuid as _uuid

        scan_id = str(_uuid.uuid4())
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

        def _worker() -> None:
            try:
                started = time.perf_counter()
                result = self.run_scan(
                    target,
                    scope_id=scope_id,
                    mode=mode,
                    reapply_ruleset=reapply_ruleset,
                    tier2=tier2,
                    options=scan_options,
                    scan_id=scan_id,
                    refs=refs,
                )
                duration_ms = int((time.perf_counter() - started) * 1000)
                total_bytes, type_breakdown = _perf_fields(result)
                state.files_scanned = result.get("files_scanned") or result.get(
                    "files_processed", 0
                ) + result.get("files_skipped", 0)
                state.findings_count = len(result["findings"])
                state.tier2_applied = result.get("tier2_applied", 0)
                state.status = "complete"
                state.current_file = None
                with self.repo.connect() as conn:
                    self.repo.update_scan_run(
                        conn,
                        scan_id,
                        status="complete",
                        files_scanned=state.files_scanned,
                        findings_count=state.findings_count,
                        tier2_applied=state.tier2_applied,
                        total_bytes=total_bytes,
                        duration_ms=duration_ms,
                        type_breakdown=type_breakdown,
                    )
                    conn.commit()
            except Exception:
                logger.exception("Scan %s failed", scan_id)
                state.status = "error"
                state.current_file = None
                with self.repo.connect() as conn:
                    self.repo.update_scan_run(
                        conn,
                        scan_id,
                        status="error",
                        files_scanned=state.files_scanned,
                        findings_count=state.findings_count,
                    )
                    conn.commit()

        import threading as _threading
        _threading.Thread(target=_worker, daemon=True).start()
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
            "current_file": None,
            "phase": None,
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
            "current_file": state.current_file,
            "phase": state.phase,
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

    def _persist_scan_progress(
        self,
        conn: sqlite3.Connection,
        *,
        scan_id: str,
        files_scanned: int,
        findings_count: int,
    ) -> None:
        conn.execute(
            """
            UPDATE scan_run
            SET files_scanned = ?, findings_count = ?, status = 'scanning'
            WHERE scan_id = ?
            """,
            (files_scanned, findings_count, scan_id),
        )
        conn.commit()

    def _tick_progress(
        self,
        scan_id: str | None,
        files_scanned: int,
        findings_count: int,
        conn: sqlite3.Connection | None = None,
        *,
        current_file: str | None = None,
        phase: str | None = None,
        persist: bool = True,
    ) -> None:
        if scan_id is None:
            return
        state = self._runs.get(scan_id)
        if state is not None:
            state.files_scanned = files_scanned
            state.findings_count = findings_count
            if current_file is not None:
                state.current_file = current_file
            state.phase = phase
        if not persist:
            # In-memory only — used on the per-file hot path so the live dashboard
            # (which reads self._runs) stays current without an fsync per file.
            return
        if conn is not None:
            self._persist_scan_progress(
                conn,
                scan_id=scan_id,
                files_scanned=files_scanned,
                findings_count=findings_count,
            )
            return
        last_exc: sqlite3.OperationalError | None = None
        for attempt in range(_PROGRESS_LOCK_RETRIES):
            try:
                with self.repo.connect() as tick_conn:
                    self._persist_scan_progress(
                        tick_conn,
                        scan_id=scan_id,
                        files_scanned=files_scanned,
                        findings_count=findings_count,
                    )
                return
            except sqlite3.OperationalError as exc:
                if "locked" not in str(exc).lower():
                    raise
                last_exc = exc
                time.sleep(min(0.05 * (2**attempt), 1.0))
        if last_exc is not None:
            raise last_exc

    def _build_modality_map(
        self,
        source: FileSource,
        refs: list[FileRef],
        scan_id: str | None,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Modality]:
        """Classify refs by modality; report phase while files_scanned is still 0."""
        modality_by_id: dict[str, Modality] = {}
        total = len(refs)
        if scan_id and total:
            self._tick_progress(scan_id, 0, 0, conn, phase=f"Classifying files… (0/{total})")
        for i, ref in enumerate(refs):
            modality_by_id[ref.file_id] = _modality_for_ref(ref, source)
            if scan_id and total:
                n = i + 1
                if n == total or n % _CLASSIFY_PROGRESS_BATCH == 0:
                    self._tick_progress(
                        scan_id,
                        0,
                        0,
                        conn,
                        phase=f"Classifying files… ({n}/{total})",
                    )
        return modality_by_id

    def _run_full_source(
        self,
        source: FileSource,
        *,
        options: ScanOptions,
        scan_id: str | None = None,
        refs: list[FileRef] | None = None,
    ) -> dict[str, Any]:
        if refs is None:
            refs = _scannable_refs(source)
        text_refs: list[FileRef]
        image_refs: list[FileRef]
        all_findings: list[dict[str, Any]] = []
        scanned = 0
        perf = _PerfAccumulator()

        workers = resolve_worker_count(options)
        pool = _DetectorPool(options)
        # Commit cadence: flush every N files so a concurrent dashboard sees
        # progress, without paying an fsync (+ WAL lock contention) per file.
        commit_every = 25

        with self.repo.connect() as conn:
            modality_by_id = self._build_modality_map(source, refs, scan_id, conn)
            text_refs = [r for r in refs if modality_by_id[r.file_id] != Modality.IMAGE]
            image_refs = [r for r in refs if modality_by_id[r.file_id] == Modality.IMAGE]

            # Warm the image ML stack only when images are present. The probe and
            # onnxruntime session loads cost ~seconds, so text-only scans skip them.
            if image_refs and options.use_ml_image:
                self._tick_progress(
                    scan_id, scanned, len(all_findings), conn, phase="Preparing image models…"
                )
                logger.info(probe_ml_image_status(use_ml_image=options.use_ml_image).summary())
                warm_image_models()

            # Detection runs concurrently (bounded by the CPU budget); writes happen
            # below in fixed ref order on this thread → deterministic finding ids.
            results: dict[str, _DetectResult | None] = {}

            def _detect(ref: FileRef) -> tuple[str, _DetectResult | None]:
                return ref.file_id, _detect_ref_safe(
                    source, ref, modality_by_id[ref.file_id], options, pool
                )

            def _on_detected(ref: FileRef, fid: str, res: _DetectResult | None) -> None:
                nonlocal scanned
                results[fid] = res
                scanned += 1
                # In-memory progress every file; persist to DB periodically only.
                self._tick_progress(
                    scan_id, scanned, 0, conn, current_file=ref.path, persist=False
                )
                if scanned % commit_every == 0:
                    self._tick_progress(scan_id, scanned, 0, conn)

            if workers <= 1:
                for ref in refs:
                    fid, res = _detect(ref)
                    _on_detected(ref, fid, res)
            else:
                with ThreadPoolExecutor(max_workers=workers) as ex:
                    futs = {ex.submit(_detect, ref): ref for ref in refs}
                    for fut in as_completed(futs):
                        ref = futs[fut]
                        fid, res = fut.result()
                        _on_detected(ref, fid, res)

            # Persist in deterministic ref order (text first, then images, each in
            # discovery order) — keeps catalog + finding ids byte-identical per run.
            for i, ref in enumerate(text_refs + image_refs, start=1):
                all_findings.extend(
                    _write_ref_result(self.repo, conn, ref, results.get(ref.file_id), self.ownership)
                )
                perf.add(ref)
                if i % commit_every == 0:
                    conn.commit()

            if _is_graph_delta_source(source):
                scope = getattr(source, "_drive_id", None)
                if scope:
                    self.repo.set_delta_token(conn, scope, source.initial_delta_token())

            conn.commit()

        return {
            "ruleset_version": app_config.RULESET_VERSION,
            "files_scanned": len(refs),
            "findings": _sort_findings(all_findings),
            "perf": perf.as_dict(),
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

    # ── Explicit Tier-2 pass (Admin-triggered) ────────────────────────────────

    def begin_tier2_pass(self, *, scope_id: str | None = None, budget: int | None = None) -> str:
        """Start an explicit Tier-2 confirmation pass in a background daemon thread.

        Returns a job_id immediately. Poll get_tier2_status(job_id) for progress.
        409 callers: check has_active_tier2_pass() before calling.
        """
        job_id = str(uuid.uuid4())
        state = Tier2JobState(job_id=job_id, status="running")
        self._tier2_runs[job_id] = state
        self._active_tier2_job_id = job_id

        def _worker() -> None:
            try:
                result = self.run_tier2_pass(scope_id=scope_id, budget=budget, _state=state)
                state.processed = result["processed"]
                state.confirmed = result["confirmed"]
                state.rejected = result["rejected"]
                state.errors = result["errors"]
                state.status = "complete"
            except Exception:
                logger.exception("Tier-2 pass %s failed", job_id)
                state.status = "error"
            finally:
                if self._active_tier2_job_id == job_id:
                    self._active_tier2_job_id = None

        threading.Thread(target=_worker, daemon=True, name=f"tier2-pass-{job_id[:8]}").start()
        return job_id

    def has_active_tier2_pass(self) -> bool:
        return self._active_tier2_job_id is not None

    def get_tier2_status(self, job_id: str) -> dict[str, Any]:
        state = self._tier2_runs.get(job_id)
        if state is None:
            raise KeyError(job_id)
        return {
            "job_id": state.job_id,
            "status": state.status,
            "processed": state.processed,
            "confirmed": state.confirmed,
            "rejected": state.rejected,
            "errors": state.errors,
        }

    def get_latest_tier2_status(self) -> dict[str, Any] | None:
        if not self._tier2_runs:
            return None
        latest_id = next(reversed(self._tier2_runs))
        return self.get_tier2_status(latest_id)

    def run_tier2_pass(
        self,
        *,
        scope_id: str | None = None,
        budget: int | None = None,
        _state: "Tier2JobState | None" = None,
    ) -> dict[str, Any]:
        """Re-read files from catalog, send ephemeral context to Tier-2, update findings.

        Only processes findings where: resolution_status='open', tier=1, and
        confidence_score falls below the risk-tiered EscalationPolicy threshold.
        """
        from app.enums import ENTRIES
        from app.services.escalation_policy import EscalationPolicy, Tier2BudgetExceeded

        max_budget = budget if budget is not None else int(os.environ.get("TIER2_BUDGET", "100"))
        policy = EscalationPolicy(max_escalations_per_run=max_budget)

        # Load all open Tier-1 findings with their catalog info.
        with self.repo.connect() as conn:
            rows = conn.execute(
                """
                SELECT f.id, f.classification_code, f.confidence_score, f.location_json,
                       f.masked_snippet, sc.path, sc.source_id, sc.native_id
                FROM finding f
                JOIN scan_catalog sc ON f.file_id = sc.file_id
                WHERE f.resolution_status = 'open' AND f.tier = 1
                ORDER BY f.risk_score DESC, f.id
                """
            ).fetchall()

        if not rows:
            return {"processed": 0, "confirmed": 0, "rejected": 0, "errors": 0}

        # Group findings by file_id (path is the grouping key).
        from collections import defaultdict

        by_path: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            entry = ENTRIES.get(row["classification_code"])
            risk_weight = entry.risk_weight if entry else "Medium"
            by_path[row["path"]].append(
                {
                    "id": row["id"],
                    "classification_code": row["classification_code"],
                    "confidence_score": float(row["confidence_score"]),
                    "risk_weight": risk_weight,
                    "location": json.loads(row["location_json"]),
                    "masked_snippet": row["masked_snippet"],
                    "source_id": row["source_id"],
                    "native_id": row["native_id"],
                    "path": row["path"],
                }
            )

        processed = 0
        confirmed = 0
        rejected = 0
        errors = 0

        with self.repo.connect() as conn:
            for path_key, findings in by_path.items():
                # Re-open the file once for all its findings.
                try:
                    file_bytes = _read_file_for_tier2(path_key, findings[0])
                except Exception:
                    logger.warning("Tier-2: cannot re-open %s — skipping", path_key)
                    errors += len(findings)
                    if _state:
                        _state.errors = errors
                    continue

                for finding in findings:
                    try:
                        if not policy.should_escalate(finding["risk_weight"], finding["confidence_score"]):
                            continue
                        policy.record_escalation()
                    except Tier2BudgetExceeded:
                        break

                    try:
                        loc = finding["location"]
                        modality = loc.get("modality", "text")

                        if modality == "image":
                            crop = _crop_image_bytes(file_bytes, loc)
                            verdict = run_tier2_image(
                                {
                                    "classification_code": finding["classification_code"],
                                    "confidence_score": finding["confidence_score"],
                                    "risk_weight": finding["risk_weight"],
                                },
                                ephemeral_crop=crop,
                            )
                        else:
                            snippet = _slice_text_context(file_bytes, loc)
                            verdict = run_tier2_text(
                                {
                                    "classification_code": finding["classification_code"],
                                    "confidence_score": finding["confidence_score"],
                                    "risk_weight": finding["risk_weight"],
                                    "masked_snippet": finding["masked_snippet"],
                                },
                                ephemeral_snippet=snippet,
                            )

                        self.repo.update_finding_tier2(
                            conn,
                            finding["id"],
                            confidence_score=verdict.confidence_score,
                            tier=2,
                            model_version=verdict.model_version,
                            prompt_hash=verdict.prompt_hash,
                        )
                        processed += 1
                        if verdict.confirmed:
                            confirmed += 1
                        else:
                            rejected += 1
                    except Exception:
                        logger.exception("Tier-2 error on finding %s", finding["id"])
                        errors += 1

                    if _state:
                        _state.processed = processed
                        _state.confirmed = confirmed
                        _state.rejected = rejected
                        _state.errors = errors

            conn.commit()

        return {"processed": processed, "confirmed": confirmed, "rejected": rejected, "errors": errors}


def _read_file_for_tier2(path: str, finding_info: dict) -> bytes:
    """Re-open a file ephemerally for Tier-2 context extraction.

    For local files: read directly from the filesystem path.
    For OneDrive files: download via GraphClient using the stored native_id.
    Bytes are never written to disk — held in memory only.
    """
    if not path.startswith("onedrive://"):
        return Path(path).read_bytes()

    # OneDrive path: onedrive://{drive_id}/{filename}
    # Requires Graph credentials + stored native_id.
    from app.sources.graph_client import GraphClient

    drive_id = finding_info.get("source_id", "")
    native_id = finding_info.get("native_id", "")
    if not native_id:
        raise ValueError(f"No native_id stored for OneDrive file: {path}")
    client = GraphClient()
    return client.download(drive_id, native_id)


def _slice_text_context(file_bytes: bytes, location: dict, window: int = 500) -> str:
    """Extract a ±window-char ephemeral context window around the finding span."""
    try:
        text = file_bytes.decode("utf-8", errors="replace")
        span = location.get("span", [0, 0])
        start = max(0, int(span[0]) - window)
        end = min(len(text), int(span[1]) + window)
        return text[start:end]
    except Exception:
        return ""


def _crop_image_bytes(file_bytes: bytes, location: dict) -> bytes:
    """Crop the image to the finding bbox; return PNG bytes or original on failure."""
    try:
        from io import BytesIO

        from PIL import Image

        bbox = location.get("bbox", [])
        if len(bbox) < 4:
            return file_bytes
        x, y, w, h = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
        img = Image.open(BytesIO(file_bytes)).convert("RGB")
        region = img.crop((x, y, x + w, y + h))
        buf = BytesIO()
        region.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        return file_bytes


def _sort_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        findings,
        key=lambda f: (f["file_id"], f.get("span", f.get("bbox", [0]))[0], f["code"]),
    )
