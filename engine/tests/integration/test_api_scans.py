from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.repositories import CatalogRepository
from app.services.scan_orchestrator import ScanOrchestrator

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_post_scans_triggers_run(tmp_path, monkeypatch):
    db = tmp_path / "catalog.sqlite"
    repo = CatalogRepository(db)
    orch = ScanOrchestrator(repo)
    monkeypatch.setattr("app.api.scans._shared_repo", repo)
    monkeypatch.setattr("app.api.scans._shared_orch", orch)
    client = TestClient(app)
    response = client.post("/scans", json={"path": str(FIXTURES), "use_config": False})
    assert response.status_code == 200
    body = response.json()
    assert "data" in body
    assert body["data"]["status"] == "complete"
    assert body["data"]["findings_count"] >= 1
