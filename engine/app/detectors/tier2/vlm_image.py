"""Tier-2 image VLM second-opinion (Story 4.3).

When GDPR_ALLOW_EXTERNAL_LLM=1 and OPENROUTER_API_KEY is set, delegates to
openrouter_client.classify() with the ephemeral image crop. Otherwise falls back
to the deterministic stub so offline CI remains green and reproducible.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

MODEL_VERSION = "tier2-vlm-stub-0.1.0"
PROMPT_TEMPLATE = "Confirm GDPR image PII classification."


@dataclass(frozen=True)
class Tier2ImageVerdict:
    confirmed: bool
    confidence_score: float
    model_version: str
    prompt_hash: str


def run_tier2_image(finding: dict, *, ephemeral_crop: bytes) -> Tier2ImageVerdict:
    """Ephemeral crop is held in memory only — never persisted."""
    from app.detectors.tier2.openrouter_client import classify, external_llm_enabled

    if external_llm_enabled() and ephemeral_crop:
        result = classify(
            context_text="",
            classification_code=finding.get("classification_code", ""),
            risk_weight=finding.get("risk_weight", "Medium"),
            modality="image",
            image_bytes=ephemeral_crop,
        )
        return Tier2ImageVerdict(
            confirmed=result["confirmed"],
            confidence_score=result["confidence"],
            model_version=result["model_version"],
            prompt_hash=result["prompt_hash"],
        )

    # Deterministic stub (offline / CI path)
    prompt_hash = hashlib.sha256(PROMPT_TEMPLATE.encode()).hexdigest()[:16]
    conf = float(finding.get("confidence_score", 0.5))
    code = finding.get("classification_code", "")
    confirmed = conf >= 0.80 or code != "FACE"
    adjusted = min(1.0, conf + (0.04 if confirmed else -0.04))
    return Tier2ImageVerdict(
        confirmed=confirmed,
        confidence_score=adjusted,
        model_version=MODEL_VERSION,
        prompt_hash=prompt_hash,
    )
