"""Scan progress tracking (Story 5.3)."""

from pathlib import Path

from app.repositories import CatalogRepository
from app.services.scan_orchestrator import ScanOrchestrator

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
