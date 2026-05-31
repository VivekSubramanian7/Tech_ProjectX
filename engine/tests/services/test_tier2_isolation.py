"""Tier-2 async isolation from Tier-1 scan path (Story 4.4)."""

from pathlib import Path

from app.repositories import CatalogRepository
from app.services.scan_orchestrator import ScanOrchestrator

ROOT = Path(__file__).resolve().parents[3]
SEED = ROOT / "data" / "enum_seed.sql"
OWNERS = ROOT / "data" / "mock_owners.json"
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_tier1_completes_without_waiting_for_tier2(tmp_path):
    repo = CatalogRepository(tmp_path / "catalog.sqlite")
    repo.init_db(SEED)
    orch = ScanOrchestrator(repo, ownership_map_path=OWNERS)

    result = orch.run_full_with_escalation(FIXTURES, tier2_enabled=True)

    assert result["tier1_complete"] is True
    assert len(result["findings"]) >= 1
    assert result["tier2_pending"] >= 0


def test_tier2_failure_does_not_abort_tier1(tmp_path, monkeypatch):
    repo = CatalogRepository(tmp_path / "catalog.sqlite")
    repo.init_db(SEED)
    orch = ScanOrchestrator(repo, ownership_map_path=OWNERS)

    def always_escalate(_self, _risk, _conf):
        return True

    def boom(_finding, *, ephemeral_snippet: str):
        raise RuntimeError("tier2 down")

    monkeypatch.setattr(
        "app.services.escalation_policy.EscalationPolicy.should_escalate",
        always_escalate,
    )
    monkeypatch.setattr(
        "app.services.scan_orchestrator.run_tier2_text",
        boom,
    )
    result = orch.run_full_with_escalation(FIXTURES, tier2_enabled=True)
    assert result["tier1_complete"] is True
    assert result["tier2_errors"] >= 1
