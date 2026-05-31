"""Risk-tiered escalation policy + budget governor (Story 4.1)."""

from __future__ import annotations

TAU_BY_RISK = {
    "Critical": 0.95,
    "High": 0.90,
    "Medium": 0.85,
    "Low": 0.75,
}


class Tier2BudgetExceeded(Exception):
    """Per-run Tier-2 escalation cap reached; caller should raise τ or queue."""


class EscalationPolicy:
    def __init__(self, *, max_escalations_per_run: int = 100) -> None:
        self.max_escalations_per_run = max_escalations_per_run
        self._escalations = 0
        self._tau_boost = 0.0

    def should_escalate(self, risk_weight: str, confidence: float) -> bool:
        if self._escalations >= self.max_escalations_per_run:
            raise Tier2BudgetExceeded("Tier-2 budget exhausted for this run")
        tau = TAU_BY_RISK.get(risk_weight, 0.85) + self._tau_boost
        return confidence < tau

    def record_escalation(self) -> None:
        self._escalations += 1
        if self._escalations >= self.max_escalations_per_run:
            self._tau_boost = 0.05
