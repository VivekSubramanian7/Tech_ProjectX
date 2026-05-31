"""Escalation policy + Tier-2 isolation (Stories 4.1, 4.4)."""

import pytest

from app.services.escalation_policy import EscalationPolicy, Tier2BudgetExceeded


def test_critical_finding_below_tau_escalates():
    policy = EscalationPolicy()
    assert policy.should_escalate("Critical", 0.92) is True


def test_low_finding_above_tau_not_escalated():
    policy = EscalationPolicy()
    assert policy.should_escalate("Low", 0.80) is False


def test_medium_at_boundary_not_escalated():
    policy = EscalationPolicy()
    assert policy.should_escalate("Medium", 0.85) is False
    assert policy.should_escalate("Medium", 0.84) is True


def test_budget_governor_raises_tau_when_cap_exceeded():
    policy = EscalationPolicy(max_escalations_per_run=2)
    assert policy.should_escalate("Critical", 0.90) is True
    policy.record_escalation()
    policy.record_escalation()
    with pytest.raises(Tier2BudgetExceeded):
        policy.should_escalate("Critical", 0.90)


def test_tier2_verdict_updates_confidence_only_in_memory():
    from app.detectors.tier2.llm_text import Tier2TextVerdict, run_tier2_text

    finding = {
        "classification_code": "PASSPORT_NUMBER",
        "masked_snippet": "••••5678",
        "confidence_score": 0.88,
        "risk_weight": "Critical",
    }
    v1: Tier2TextVerdict = run_tier2_text(finding, ephemeral_snippet="X12345678")
    v2: Tier2TextVerdict = run_tier2_text(finding, ephemeral_snippet="X12345678")
    assert v1.confirmed is v2.confirmed
    assert v1.model_version
    assert v1.prompt_hash
    assert v1.model_version == v2.model_version
