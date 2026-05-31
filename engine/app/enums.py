"""Generated from enum/classification_enum.yaml — do not edit by hand."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ClassificationEntry:
    machine_code: str
    display_label: str
    modality: str
    mvp: bool
    risk_weight: str
    gdpr_focus: str


ENTRIES: dict[str, ClassificationEntry] = {
    "PERSON_NAME": ClassificationEntry(machine_code="PERSON_NAME", display_label='Full name', modality="text", mvp=True, risk_weight="Medium", gdpr_focus='Art.5/17'),
    "USERNAME": ClassificationEntry(machine_code="USERNAME", display_label='Username / login', modality="text", mvp=True, risk_weight="Low", gdpr_focus='Art.5/17'),
    "EMAIL": ClassificationEntry(machine_code="EMAIL", display_label='Email address', modality="text", mvp=True, risk_weight="Medium", gdpr_focus='Art.5/17'),
    "SIGNATURE": ClassificationEntry(machine_code="SIGNATURE", display_label='Signature', modality="image", mvp=True, risk_weight="High", gdpr_focus='Art.5/17/9-adj'),
    "FACE": ClassificationEntry(machine_code="FACE", display_label='Photo of a person', modality="image", mvp=True, risk_weight="High", gdpr_focus='Art.9 (biometric)'),
    "PHONE_NUMBER": ClassificationEntry(machine_code="PHONE_NUMBER", display_label='Phone number', modality="text", mvp=True, risk_weight="Medium", gdpr_focus='Art.5/17'),
    "FAX_NUMBER": ClassificationEntry(machine_code="FAX_NUMBER", display_label='Fax number', modality="text", mvp=True, risk_weight="Low", gdpr_focus='Art.5/17'),
    "HOME_ADDRESS": ClassificationEntry(machine_code="HOME_ADDRESS", display_label='Home address', modality="text", mvp=True, risk_weight="High", gdpr_focus='Art.5/17'),
    "BILLING_SHIPPING_ADDRESS": ClassificationEntry(machine_code="BILLING_SHIPPING_ADDRESS", display_label='Billing / shipping address', modality="text", mvp=True, risk_weight="Medium", gdpr_focus='Art.5/17'),
    "PASSPORT_NUMBER": ClassificationEntry(machine_code="PASSPORT_NUMBER", display_label='Passport number', modality="text", mvp=True, risk_weight="Critical", gdpr_focus='Art.5/17/32'),
    "DE_PERSONALAUSWEIS": ClassificationEntry(machine_code="DE_PERSONALAUSWEIS", display_label='German ID card number', modality="text", mvp=True, risk_weight="Critical", gdpr_focus='Art.5/17/32'),
    "DRIVERS_LICENSE_NUMBER": ClassificationEntry(machine_code="DRIVERS_LICENSE_NUMBER", display_label="Driver's licence number", modality="text", mvp=True, risk_weight="High", gdpr_focus='Art.5/17/32'),
    "TRAVEL_HISTORY": ClassificationEntry(machine_code="TRAVEL_HISTORY", display_label='Travel history', modality="text", mvp=True, risk_weight="Medium", gdpr_focus='Art.5/17'),
    "IBAN": ClassificationEntry(machine_code="IBAN", display_label='Bank account (IBAN)', modality="text", mvp=True, risk_weight="High", gdpr_focus='Art.5/17/32'),
    "CREDIT_CARD_NUMBER": ClassificationEntry(machine_code="CREDIT_CARD_NUMBER", display_label='Payment card number', modality="text", mvp=True, risk_weight="Critical", gdpr_focus='Art.5/17/32'),
    "IP_ADDRESS": ClassificationEntry(machine_code="IP_ADDRESS", display_label='IP address', modality="text", mvp=True, risk_weight="Low", gdpr_focus='Art.5/17'),
    "EMPLOYEE_ID": ClassificationEntry(machine_code="EMPLOYEE_ID", display_label='Employee / personnel ID', modality="text", mvp=True, risk_weight="Medium", gdpr_focus='Art.5/17'),
    "LICENSE_PLATE": ClassificationEntry(machine_code="LICENSE_PLATE", display_label='Vehicle licence plate', modality="image", mvp=True, risk_weight="Medium", gdpr_focus='Art.5/17'),
    "DE_SOZIALVERSICHERUNGSNR": ClassificationEntry(machine_code="DE_SOZIALVERSICHERUNGSNR", display_label='German social security number', modality="text", mvp=True, risk_weight="Critical", gdpr_focus='Art.5/17/32'),
    "DE_STEUER_ID": ClassificationEntry(machine_code="DE_STEUER_ID", display_label='German tax ID', modality="text", mvp=True, risk_weight="High", gdpr_focus='Art.5/17/32'),
    "DATE_OF_BIRTH": ClassificationEntry(machine_code="DATE_OF_BIRTH", display_label='Date of birth', modality="text", mvp=False, risk_weight="Medium", gdpr_focus='Art.5/17'),
    "PLACE_OF_BIRTH": ClassificationEntry(machine_code="PLACE_OF_BIRTH", display_label='Place of birth', modality="text", mvp=False, risk_weight="Low", gdpr_focus='Art.5/17'),
    "NATIONALITY": ClassificationEntry(machine_code="NATIONALITY", display_label='Nationality', modality="text", mvp=False, risk_weight="Medium", gdpr_focus='Art.5/17'),
    "GENDER": ClassificationEntry(machine_code="GENDER", display_label='Gender', modality="text", mvp=False, risk_weight="Low", gdpr_focus='Art.5/17'),
    "MARITAL_STATUS": ClassificationEntry(machine_code="MARITAL_STATUS", display_label='Marital status', modality="text", mvp=False, risk_weight="Low", gdpr_focus='Art.5/17'),
    "HEALTH_INSURANCE_NUMBER": ClassificationEntry(machine_code="HEALTH_INSURANCE_NUMBER", display_label='Health insurance number', modality="text", mvp=False, risk_weight="High", gdpr_focus='Art.9-adj'),
    "DEVICE_LOCATION": ClassificationEntry(machine_code="DEVICE_LOCATION", display_label='Device / location data', modality="text", mvp=False, risk_weight="Medium", gdpr_focus='Art.5/17'),
    "NON_DE_NATIONAL_ID": ClassificationEntry(machine_code="NON_DE_NATIONAL_ID", display_label='National ID (non-DE)', modality="text", mvp=False, risk_weight="High", gdpr_focus='Art.5/17/32'),
    "NON_DE_TAX_ID": ClassificationEntry(machine_code="NON_DE_TAX_ID", display_label='Tax ID (non-DE)', modality="text", mvp=False, risk_weight="High", gdpr_focus='Art.5/17/32'),
    "RACIAL_ETHNIC_ORIGIN": ClassificationEntry(machine_code="RACIAL_ETHNIC_ORIGIN", display_label='Racial / ethnic origin', modality="text", mvp=False, risk_weight="Critical", gdpr_focus='Art.9'),
    "POLITICAL_OPINION": ClassificationEntry(machine_code="POLITICAL_OPINION", display_label='Political opinion', modality="text", mvp=False, risk_weight="Critical", gdpr_focus='Art.9'),
    "RELIGIOUS_BELIEF": ClassificationEntry(machine_code="RELIGIOUS_BELIEF", display_label='Religious / philosophical belief', modality="text", mvp=False, risk_weight="Critical", gdpr_focus='Art.9'),
    "TRADE_UNION_MEMBERSHIP": ClassificationEntry(machine_code="TRADE_UNION_MEMBERSHIP", display_label='Trade-union membership', modality="text", mvp=False, risk_weight="Critical", gdpr_focus='Art.9'),
    "GENETIC_DATA": ClassificationEntry(machine_code="GENETIC_DATA", display_label='Genetic data', modality="text", mvp=False, risk_weight="Critical", gdpr_focus='Art.9'),
    "BIOMETRIC_DATA": ClassificationEntry(machine_code="BIOMETRIC_DATA", display_label='Biometric data', modality="image", mvp=False, risk_weight="Critical", gdpr_focus='Art.9'),
    "HEALTH_DATA": ClassificationEntry(machine_code="HEALTH_DATA", display_label='Health data', modality="text", mvp=False, risk_weight="Critical", gdpr_focus='Art.9'),
    "SEX_LIFE_ORIENTATION": ClassificationEntry(machine_code="SEX_LIFE_ORIENTATION", display_label='Sex life / sexual orientation', modality="text", mvp=False, risk_weight="Critical", gdpr_focus='Art.9'),
}

MVP_TEXT_CODES = frozenset(
    e.machine_code for e in ENTRIES.values() if e.mvp and e.modality == 'text'
)


def lookup(machine_code: str) -> ClassificationEntry:
    """Resolve a machine_code to its enum row."""
    return ENTRIES[machine_code]

