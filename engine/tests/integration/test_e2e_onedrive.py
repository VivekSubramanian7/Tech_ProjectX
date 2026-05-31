"""OneDrive fixture end-to-end (Stories 6.1, 6.2)."""

from pathlib import Path

from app.repositories import CatalogRepository
from app.services.scan_orchestrator import ScanOrchestrator
from app.sources.onedrive_graph import OneDriveGraphSource

ROOT = Path(__file__).resolve().parents[3]
SEED = ROOT / "data" / "enum_seed.sql"
OWNERS = ROOT / "data" / "mock_owners.json"
FIXTURE = ROOT / "data" / "onedrive_fixture.json"


def _orch(tmp_path: Path) -> ScanOrchestrator:
    repo = CatalogRepository(tmp_path / "catalog.sqlite")
    repo.init_db(SEED)
    return ScanOrchestrator(repo, ownership_map_path=OWNERS)


def test_onedrive_full_scan_via_file_source(tmp_path: Path):
    source = OneDriveGraphSource.from_fixture(FIXTURE)
    orch = _orch(tmp_path)
    result = orch.run_scan(source, scope_id=source._drive_id, mode="full")

    assert result["files_scanned"] >= 2
    codes = {f["code"] for f in result["findings"]}
    assert "EMAIL" in codes


def test_onedrive_graph_delta_processes_changes(tmp_path: Path):
    source = OneDriveGraphSource.from_fixture(FIXTURE)
    orch = _orch(tmp_path)
    scope = source._drive_id

    orch.run_scan(source, scope_id=scope, mode="full")
    delta = orch.run_scan(source, scope_id=scope, mode="delta")

    assert delta["files_processed"] >= 1
    assert delta.get("delta_changes", 0) >= 1

    with orch.repo.connect() as conn:
        token = orch.repo.get_delta_token(conn, scope)
        assert token == "delta-v2"
