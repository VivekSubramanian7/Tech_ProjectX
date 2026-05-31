import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "eval"))
from determinism import assert_deterministic

from app.repositories import CatalogRepository
from app.services.scan_orchestrator import ScanOrchestrator

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
ROOT = Path(__file__).resolve().parents[3]
SEED = ROOT / "data" / "enum_seed.sql"
OWNERS = ROOT / "data" / "mock_owners.json"


def test_full_scan_populates_catalog_and_findings(tmp_path):
    db = tmp_path / "catalog.sqlite"
    repo = CatalogRepository(db)
    repo.init_db(SEED)
    orch = ScanOrchestrator(repo, ownership_map_path=OWNERS)
    result = orch.run_full(FIXTURES)

    assert result["ruleset_version"]
    assert result["files_scanned"] >= 1
    assert len(result["findings"]) >= 1

    with repo.connect() as conn:
        assert repo.count_catalog(conn) >= 1
        rows = repo.list_findings(conn)
        assert rows
        catalog = conn.execute(
            "SELECT scan_status, ruleset_version FROM scan_catalog"
        ).fetchall()
        assert all(r["scan_status"] == "complete" for r in catalog)
        assert all(r["ruleset_version"] for r in catalog)


def test_full_scan_is_deterministic(tmp_path):
    db = tmp_path / "catalog.sqlite"
    repo = CatalogRepository(db)
    repo.init_db(SEED)
    orch = ScanOrchestrator(repo, ownership_map_path=OWNERS)

    assert_deterministic(orch.tier1_scan_callable(FIXTURES), runs=10)
