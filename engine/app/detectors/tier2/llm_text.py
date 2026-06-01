"""Tier-2 text LLM second-opinion (Story 4.2).

When GDPR_ALLOW_EXTERNAL_LLM=1 and OPENROUTER_API_KEY is set, delegates to
openrouter_client.classify(). Otherwise falls back to the deterministic stub
so offline CI and all existing tests remain green and reproducible.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

MODEL_VERSION = "tier2-llm-stub-0.1.0"
PROMPT_TEMPLATE = "Confirm GDPR PII classification for masked snippet."


@dataclass(frozen=True)
class Tier2TextVerdict:
    confirmed: bool
    confidence_score: float
    model_version: str
    prompt_hash: str


def run_tier2_text(finding: dict, *, ephemeral_snippet: str) -> Tier2TextVerdict:
    """Ephemeral snippet is held in memory only — never persisted."""
    from app.detectors.tier2.openrouter_client import classify, external_llm_enabled

    if external_llm_enabled():
        result = classify(
            context_text=ephemeral_snippet,
            classification_code=finding.get("classification_code", ""),
            risk_weight=finding.get("risk_weight", "Medium"),
            modality="text",
        )
        return Tier2TextVerdict(
            confirmed=result["confirmed"],
            confidence_score=result["confidence"],
            model_version=result["model_version"],
            prompt_hash=result["prompt_hash"],
        )

    # Deterministic stub (offline / CI path)
    prompt_hash = hashlib.sha256(PROMPT_TEMPLATE.encode()).hexdigest()[:16]
    conf = float(finding.get("confidence_score", 0.5))
    risk = finding.get("risk_weight", "Medium")
    confirmed = conf >= 0.85 or risk != "Critical"
    adjusted = min(1.0, conf + (0.05 if confirmed else -0.05))
    return Tier2TextVerdict(
        confirmed=confirmed,
        confidence_score=adjusted,
        model_version=MODEL_VERSION,
        prompt_hash=prompt_hash,
    )
