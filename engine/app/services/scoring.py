"""Dual scoring: risk from enum weight, confidence from detector."""

from __future__ import annotations

from app.enums import lookup

RISK_NUMERIC = {
    "Critical": 4.0,
    "High": 3.0,
    "Medium": 2.0,
    "Low": 1.0,
}


def risk_score_for_code(classification_code: str) -> float:
    entry = lookup(classification_code)
    return RISK_NUMERIC[entry.risk_weight]


def final_scores(classification_code: str, confidence_score: float) -> tuple[float, float]:
    """Return (risk_score, confidence_score) as independent values."""
    return risk_score_for_code(classification_code), confidence_score
