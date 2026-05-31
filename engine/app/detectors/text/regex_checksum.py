"""Tier-1 deterministic regex and checksum detectors."""

from __future__ import annotations

import re
from re import Pattern

from app.config import DETECTOR_VERSION
from app.detectors.base import Detection, TextSpan, mask_value
from app.enums import MVP_TEXT_CODES

# Patterns (simplified DE + international formats)
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
IBAN_RE = re.compile(
    r"\bDE\d{2}\s?(?:\d{4}\s?){4}\d{2}\b",
    re.IGNORECASE,
)
IP_RE = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d?\d)\b"
)
DE_STEUER_RE = re.compile(r"\b\d{11}\b")
DE_STEUER_LABELED_RE = re.compile(r"Steuer[- ]?ID:\s*(\d{11})\b", re.IGNORECASE)
DE_SVNR_RE = re.compile(r"\b\d{8}\s?\d{2}\s?[A-Z]\s?\d{3}\b", re.IGNORECASE)
PASSPORT_RE = re.compile(r"\b[A-Z]{1,2}\d{6,9}\b")
PAN_RE = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
# Require card-like grouping to avoid matching arbitrary digit runs in IBANs.
PAN_CONTEXT_RE = re.compile(
    r"\b(?:\d{4}[ -]?){3}\d{1,7}\b"
)
PHONE_RE = re.compile(r"\b(?:\+49|0)[1-9][\d\s/-]{7,14}\b")
FAX_RE = re.compile(
    r"\b[Ff]ax(?:nummer)?[:\s]+((?:\+49|0)[\d\s/-]{7,14})\b"
)
USERNAME_RE = re.compile(
    r"\b(?:Username|Login|Benutzername)[:\s]+([A-Za-z0-9_.@-]{3,})\b",
    re.IGNORECASE,
)
DE_PERSONALAUSWEIS_RE = re.compile(r"\b[A-Z]\d{2}[A-Z0-9]{7}\b")
DRIVERS_LICENSE_LABELED_RE = re.compile(
    r"(?:licen[cs]e|Führerschein|Fuehrerschein)[^\w]*([A-Z0-9]{9,12})\b",
    re.IGNORECASE,
)
DRIVERS_LICENSE_RE = re.compile(r"\b[A-Z]\d{3}[A-Z]{3}\d[A-Z0-9]\d{2}\b")


def _luhn_valid(number: str) -> bool:
    digits = [int(c) for c in number if c.isdigit()]
    if len(digits) < 13:
        return False
    checksum = 0
    parity = len(digits) % 2
    for i, d in enumerate(digits):
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


def _de_steuer_valid(raw: str) -> bool:
    """Bundeszentralamt für Steuern check-digit rules for 11-digit Steuer-ID."""
    digits = [int(c) for c in raw if c.isdigit()]
    if len(digits) != 11 or digits[0] == 0:
        return False
    weights = [10, 9, 8, 7, 6, 5, 4, 3, 2]
    total = sum(d * w for d, w in zip(digits[:10], weights, strict=False))
    remainder = total % 11
    if remainder == 1:
        return False
    check = 11 - remainder if remainder != 0 else 11
    if check == 10:
        check = 0
    if check == 11:
        check = 0
    return digits[10] == check


def _emit(
    code: str,
    text: str,
    start: int,
    end: int,
    base_offset: int,
    confidence: float,
) -> Detection:
    if code not in MVP_TEXT_CODES:
        raise ValueError(f"Unknown classification code: {code}")
    raw = text[start:end]
    return Detection(
        classification_code=code,
        span=TextSpan(start=base_offset + start, end=base_offset + end),
        confidence_score=confidence,
        masked_snippet=mask_value(raw),
        detector_version=DETECTOR_VERSION,
    )


def _scan_pattern(
    code: str,
    text: str,
    pattern: Pattern[str],
    base_offset: int,
    *,
    validator=None,
    base_confidence: float = 0.99,
) -> list[Detection]:
    out: list[Detection] = []
    for m in pattern.finditer(text):
        raw = m.group(0)
        if validator and not validator(raw):
            continue
        out.append(_emit(code, text, m.start(), m.end(), base_offset, base_confidence))
    return out


class RegexChecksumDetector:
    detector_version = DETECTOR_VERSION

    def detect(self, text: str, base_offset: int = 0) -> list[Detection]:
        findings: list[Detection] = []
        findings.extend(_scan_pattern("EMAIL", text, EMAIL_RE, base_offset))
        findings.extend(_scan_pattern("IBAN", text, IBAN_RE, base_offset))
        findings.extend(_scan_pattern("IP_ADDRESS", text, IP_RE, base_offset))
        for m in DE_STEUER_LABELED_RE.finditer(text):
            raw = m.group(1)
            if _de_steuer_valid(raw):
                findings.append(
                    _emit(
                        "DE_STEUER_ID",
                        text,
                        m.start(1),
                        m.end(1),
                        base_offset,
                        0.99,
                    )
                )
        for m in DE_STEUER_RE.finditer(text):
            raw = m.group(0)
            if not _de_steuer_valid(raw):
                continue
            if any(f.span.start == base_offset + m.start() for f in findings if f.classification_code == "DE_STEUER_ID"):
                continue
            findings.append(
                _emit("DE_STEUER_ID", text, m.start(), m.end(), base_offset, 0.99)
            )
        findings.extend(_scan_pattern("DE_SOZIALVERSICHERUNGSNR", text, DE_SVNR_RE, base_offset))
        findings.extend(_scan_pattern("PASSPORT_NUMBER", text, PASSPORT_RE, base_offset))
        findings.extend(_scan_pattern("PHONE_NUMBER", text, PHONE_RE, base_offset))
        for m in FAX_RE.finditer(text):
            findings.append(
                _emit("FAX_NUMBER", text, m.start(1), m.end(1), base_offset, 0.95)
            )
        for m in USERNAME_RE.finditer(text):
            findings.append(
                _emit("USERNAME", text, m.start(1), m.end(1), base_offset, 0.9)
            )
        findings.extend(
            _scan_pattern("DE_PERSONALAUSWEIS", text, DE_PERSONALAUSWEIS_RE, base_offset, base_confidence=0.97)
        )
        for m in DRIVERS_LICENSE_LABELED_RE.finditer(text):
            findings.append(
                _emit("DRIVERS_LICENSE_NUMBER", text, m.start(1), m.end(1), base_offset, 0.96)
            )
        for m in DRIVERS_LICENSE_RE.finditer(text):
            if any(
                f.span.start == base_offset + m.start()
                for f in findings
                if f.classification_code == "DRIVERS_LICENSE_NUMBER"
            ):
                continue
            findings.append(
                _emit("DRIVERS_LICENSE_NUMBER", text, m.start(), m.end(), base_offset, 0.94)
            )
        for m in PAN_CONTEXT_RE.finditer(text):
            raw = m.group(0)
            if not _luhn_valid(raw):
                continue
            findings.append(
                _emit(
                    "CREDIT_CARD_NUMBER",
                    text,
                    m.start(),
                    m.end(),
                    base_offset,
                    0.99,
                )
            )
        return findings
