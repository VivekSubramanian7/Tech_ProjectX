"""OpenRouter LLM client for Tier-2 GDPR PII confirmation.

Safety gate: this module sends content to a THIRD-PARTY API (OpenRouter).
It is disabled unless GDPR_ALLOW_EXTERNAL_LLM=1 is explicitly set.
For production deployments use in-perimeter inference behind the same interface.

Env vars:
  OPENROUTER_API_KEY        — required when enabled
  OPENROUTER_MODEL          — model string (default: anthropic/claude-3.5-haiku)
  OPENROUTER_BASE_URL       — base URL (default: https://openrouter.ai/api/v1)
  OPENROUTER_TIMEOUT_S      — request timeout in seconds (default: 30)
  GDPR_ALLOW_EXTERNAL_LLM   — must be "1" to enable
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any

import httpx

_DEFAULT_MODEL = "anthropic/claude-3.5-haiku"
_DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
_DEFAULT_TIMEOUT = 30

_SYSTEM_PROMPT = (
    "You are a GDPR compliance assistant. "
    "Analyse the provided text context and determine whether it contains the "
    "specified PII classification. "
    "Respond ONLY with valid JSON matching the given schema. "
    "Do not include any other text."
)

_USER_TEMPLATE = """\
Classification: {classification_code}
Risk level: {risk_weight}

Context (may be partially masked):
\"\"\"
{context_text}
\"\"\"

Does this context confirm the presence of {classification_code} PII?
Provide a brief rationale (1-2 sentences)."""

_IMAGE_TEMPLATE = """\
Classification: {classification_code}
Risk level: {risk_weight}

An image region has been identified as potentially containing {classification_code}.
Based on the image crop provided, confirm whether this is genuine GDPR-relevant PII.
Provide a brief rationale (1-2 sentences)."""

_JSON_SCHEMA = {
    "name": "tier2_verdict",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "confirmed": {"type": "boolean"},
            "confidence": {"type": "number"},
            "rationale": {"type": "string"},
        },
        "required": ["confirmed", "confidence", "rationale"],
        "additionalProperties": False,
    },
}


def external_llm_enabled() -> bool:
    """True only when API key is set AND the explicit opt-in flag is 1."""
    return (
        bool(os.environ.get("OPENROUTER_API_KEY"))
        and os.environ.get("GDPR_ALLOW_EXTERNAL_LLM", "0").strip() == "1"
    )


def classify(
    *,
    context_text: str,
    classification_code: str,
    risk_weight: str,
    modality: str = "text",
    image_bytes: bytes | None = None,
) -> dict[str, Any]:
    """Call OpenRouter to confirm/reject a Tier-1 finding.

    Returns a dict with keys: confirmed (bool), confidence (float 0-1),
    rationale (str), model_version (str), prompt_hash (str).

    The context_text / image_bytes are held in memory only — never persisted.
    """
    api_key = os.environ["OPENROUTER_API_KEY"]
    model = os.environ.get("OPENROUTER_MODEL", _DEFAULT_MODEL)
    base_url = os.environ.get("OPENROUTER_BASE_URL", _DEFAULT_BASE_URL).rstrip("/")
    timeout = float(os.environ.get("OPENROUTER_TIMEOUT_S", _DEFAULT_TIMEOUT))

    if modality == "image" and image_bytes:
        user_content: Any = [
            {
                "type": "text",
                "text": _IMAGE_TEMPLATE.format(
                    classification_code=classification_code,
                    risk_weight=risk_weight,
                ),
            },
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{_b64(image_bytes)}",
                },
            },
        ]
        prompt_source = _IMAGE_TEMPLATE.format(
            classification_code=classification_code, risk_weight=risk_weight
        )
    else:
        user_content = _USER_TEMPLATE.format(
            classification_code=classification_code,
            risk_weight=risk_weight,
            context_text=context_text[:2000],  # cap to avoid huge tokens
        )
        prompt_source = user_content

    prompt_hash = hashlib.sha256(f"{model}:{prompt_source}".encode()).hexdigest()[:16]

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "response_format": {"type": "json_schema", "json_schema": _JSON_SCHEMA},
        "temperature": 0,
    }

    resp = httpx.post(
        f"{base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/VivekSubramanian7/Tech_ProjectX",
            "X-Title": "Bosch GDPR Discovery",
        },
        content=json.dumps(payload),
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()

    raw = data["choices"][0]["message"]["content"]
    verdict = json.loads(raw)

    return {
        "confirmed": bool(verdict.get("confirmed", False)),
        "confidence": float(verdict.get("confidence", 0.5)),
        "rationale": str(verdict.get("rationale", "")),
        "model_version": f"openrouter:{model}",
        "prompt_hash": prompt_hash,
    }


def _b64(data: bytes) -> str:
    import base64

    return base64.b64encode(data).decode()
