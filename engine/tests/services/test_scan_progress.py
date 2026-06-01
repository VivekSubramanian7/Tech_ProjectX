"""Scan progress tracking (Story 5.3)."""

import time
from pathlib import Path
from unittest.mock import MagicMock

from app.detectors.router import Modality
from app.repositories import CatalogRepository
from app.services.scan_orchestrator import (
    ScanOrchestrator,
    ScanRunState,
    _modality_for_ref,
    _scannable_refs,
)
from app.sources.local_folder import LocalFolderSource

ROOT = Path(__file__).resolve().parents[3]
SEED = ROOT / "data" / "enum_seed.sql"
OWNERS = ROOT / "data" / "mock_owners.json"
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_scan_run_tracks_progress(tmp_path):
    repo = CatalogRepository(tmp_path / "catalog.sqlite")
    repo.init_db(SEED)
    orch = ScanOrchestrator(repo, ownership_map_path=OWNERS)

    run_id = orch.start_full(FIXTURES)
    status = orch.get_scan_status(run_id)

    assert status["status"] == "complete"
    assert status["files_total"] >= 1
    assert status["files_scanned"] == status["files_total"]
    assert status["findings_count"] >= 1


def test_scan_status_persisted_in_db(tmp_path):
    repo = CatalogRepository(tmp_path / "catalog.sqlite")
    repo.init_db(SEED)
    orch = ScanOrchestrator(repo, ownership_map_path=OWNERS)

    run_id = orch.start_full(FIXTURES)
    orch2 = ScanOrchestrator(repo, ownership_map_path=OWNERS)
    status = orch2.get_scan_status(run_id)

    assert status["status"] == "complete"
    assert status["findings_count"] >= 1


def test_get_scan_status_unknown_raises(tmp_path):
    repo = CatalogRepository(tmp_path / "catalog.sqlite")
    repo.init_db(SEED)
    orch = ScanOrchestrator(repo, ownership_map_path=OWNERS)

    try:
        orch.get_scan_status("nonexistent-id")
        raised = False
    except KeyError:
        raised = True
    assert raised


def test_modality_for_ref_skips_open_for_non_pdf(tmp_path):
    txt = tmp_path / "note.txt"
    txt.write_text("hello world", encoding="utf-8")
    source = LocalFolderSource(tmp_path)
    refs = _scannable_refs(source)
    assert len(refs) == 1
    ref = refs[0]

    source.open = MagicMock(wraps=source.open)  # type: ignore[method-assign]
    assert _modality_for_ref(ref, source) == Modality.TEXT
    source.open.assert_not_called()


def test_run_full_source_reuses_refs_without_relisting(tmp_path, monkeypatch):
    repo = CatalogRepository(tmp_path / "catalog.sqlite")
    repo.init_db(SEED)
    orch = ScanOrchestrator(repo, ownership_map_path=OWNERS)
    source = LocalFolderSource(FIXTURES)
    refs = _scannable_refs(source)

    list_calls: list[int] = []

    def counting_scannable(src):  # noqa: ARG001
        list_calls.append(1)
        return _scannable_refs(source)

    monkeypatch.setattr(
        "app.services.scan_orchestrator._scannable_refs",
        counting_scannable,
    )
    orch._run_full_source(source, options=orch.default_options, refs=refs)
    assert list_calls == []


def test_build_modality_map_reports_phase(tmp_path):
    repo = CatalogRepository(tmp_path / "catalog.sqlite")
    repo.init_db(SEED)
    orch = ScanOrchestrator(repo, ownership_map_path=OWNERS)
    source = LocalFolderSource(FIXTURES)
    refs = _scannable_refs(source)
    scan_id = "phase-test-id"
    orch._runs[scan_id] = ScanRunState(
        scan_id=scan_id, status="scanning", files_total=len(refs), mode="full"
    )

    orch._build_modality_map(source, refs, scan_id)
    status = orch.get_scan_status(scan_id)
    assert status["files_scanned"] == 0
    assert status["phase"] is not None
    assert "Classifying" in status["phase"]


def test_begin_scan_phase_or_progress_before_complete(tmp_path):
    repo = CatalogRepository(tmp_path / "catalog.sqlite")
    repo.init_db(SEED)
    orch = ScanOrchestrator(repo, ownership_map_path=OWNERS)

    scan_id = orch.begin_scan(FIXTURES)
    saw_activity = False
    deadline = time.time() + 30.0
    final = None
    while time.time() < deadline:
        final = orch.get_scan_status(scan_id)
        if final.get("phase") or final.get("files_scanned", 0) > 0:
            saw_activity = True
        if final["status"] in ("complete", "error"):
            break
        time.sleep(0.05)

    assert final is not None
    assert final["status"] == "complete"
    assert saw_activity or final["files_scanned"] == final["files_total"]
