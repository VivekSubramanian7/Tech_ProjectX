import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.repositories import CatalogRepository
from app.services.scan_orchestrator import ScanOrchestrator

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _wait_for_scan(client: TestClient, scan_id: str, timeout: float = 20.0) -> None:
    """Poll until the background scan completes (begin_scan runs off-thread)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = client.get(f"/scans/{scan_id}").json()["data"]["status"]
        if status in {"complete", "error"}:
            return
        time.sleep(0.1)
    raise AssertionError(f"scan {scan_id} did not complete within {timeout}s")


def test_admin_reset_clears_catalog(tmp_path, monkeypatch):
    db = tmp_path / "catalog.sqlite"
    repo = CatalogRepository(db)
    orch = ScanOrchestrator(repo)
    monkeypatch.setattr("app.api.scans._shared_repo", repo)
    monkeypatch.setattr("app.api.scans._shared_orch", orch)
    monkeypatch.setattr("app.api.aggregates._repo", repo)

    client = TestClient(app)
    scan_id = client.post("/scans", json={"path": str(FIXTURES), "use_config": False}).json()["meta"][
        "scan_id"
    ]
    _wait_for_scan(client, scan_id)
    before = client.get("/aggregates").json()["data"]
    assert before["total_findings"] >= 1

    response = client.post("/aggregates/reset")
    assert response.status_code == 200
    assert response.json()["data"]["reset"] is True

    after = client.get("/aggregates").json()["data"]
    assert after["files_scanned"] == 0
    assert after["open_findings"] == 0
    assert after["total_findings"] == 0
    assert after["assurance_pct"] == 0.0
    assert client.get("/scans").json()["data"] == []
