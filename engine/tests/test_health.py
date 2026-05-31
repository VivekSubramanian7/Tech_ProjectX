from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_200():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_pytest_collects_engine():
    assert True
