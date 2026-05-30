"""Minimal classification-enum reference for the eval harness.

Seeded from `_bmad-output/pii-detection-scope.md` (P1 canonical + MVP P2 rows).
Provides each code's display label, risk weight, and modality — the harness needs
risk_weight for severity-stratified recall (Story 2.2).

NOTE: This is a self-contained copy so Epic 2 can be built and tested before Epic 1.
Epic 1 Story 1.2 (`enum/classification_enum.yaml` + `enum/generate.py`) becomes the
real single source of truth; this module will then be generated from it, not hand-kept.
"""
from __future__ import annotations

# code -> (display_label, risk_weight, modality)
ENUM: dict[str, dict[str, str]] = {
    # --- Priority 1 (canonical, from case study) ---
    "PERSON_NAME": {"display_label": "Full name", "risk_weight": "Medium", "modality": "text"},
    "USERNAME": {"display_label": "Username / login", "risk_weight": "Low", "modality": "text"},
    "EMAIL": {"display_label": "Email address", "risk_weight": "Medium", "modality": "text"},
    "SIGNATURE": {"display_label": "Signature", "risk_weight": "High", "modality": "image"},
    "FACE": {"display_label": "Photo of a person", "risk_weight": "High", "modality": "image"},
    "PHONE_NUMBER": {"display_label": "Phone number", "risk_weight": "Medium", "modality": "text"},
    "FAX_NUMBER": {"display_label": "Fax number", "risk_weight": "Low", "modality": "text"},
    "HOME_ADDRESS": {"display_label": "Home address", "risk_weight": "High", "modality": "text"},
    "BILLING_SHIPPING_ADDRESS": {"display_label": "Billing / shipping address", "risk_weight": "Medium", "modality": "text"},
    "PASSPORT_NUMBER": {"display_label": "Passport number", "risk_weight": "Critical", "modality": "text"},
    "DE_PERSONALAUSWEIS": {"display_label": "German ID card number", "risk_weight": "Critical", "modality": "text"},
    "DRIVERS_LICENSE_NUMBER": {"display_label": "Driver's licence number", "risk_weight": "High", "modality": "text"},
    "TRAVEL_HISTORY": {"display_label": "Travel history", "risk_weight": "Medium", "modality": "text"},
    # --- Priority 2 (general identifiers, MVP-scoped) ---
    "IBAN": {"display_label": "Bank account (IBAN)", "risk_weight": "High", "modality": "text"},
    "CREDIT_CARD_NUMBER": {"display_label": "Payment card number", "risk_weight": "Critical", "modality": "text"},
    "IP_ADDRESS": {"display_label": "IP address", "risk_weight": "Low", "modality": "text"},
    "EMPLOYEE_ID": {"display_label": "Employee / personnel ID", "risk_weight": "Medium", "modality": "text"},
    "LICENSE_PLATE": {"display_label": "Vehicle licence plate", "risk_weight": "Medium", "modality": "image"},
    "DE_SOZIALVERSICHERUNGSNR": {"display_label": "German social security number", "risk_weight": "Critical", "modality": "text"},
    "DE_STEUER_ID": {"display_label": "German tax ID", "risk_weight": "High", "modality": "text"},
}

# Risk weights, ordered most→least severe. "Critical" is the top-severity tier
# that NFR9 gates separately.
RISK_ORDER = ["Critical", "High", "Medium", "Low"]
TOP_SEVERITY = "Critical"


def risk_weight(code: str) -> str:
    """Return the risk weight for a classification code."""
    return ENUM[code]["risk_weight"]
