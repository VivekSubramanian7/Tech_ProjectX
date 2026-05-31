"""CI gate: detector-emitted codes must exist in generated enum."""

from __future__ import annotations

import re
from pathlib import Path

from app.enums import ENTRIES

ROOT = Path(__file__).resolve().parents[2]
DETECTORS_DIR = ROOT / "engine" / "app" / "detectors"

CODE_PATTERN = re.compile(r'classification_code\s*=\s*["\']([A-Z0-9_]+)["\']')
ENUM_LITERAL = re.compile(r'["\']([A-Z][A-Z0-9_]{2,})["\']')


def _codes_in_detectors() -> set[str]:
    found: set[str] = set()
    if not DETECTORS_DIR.exists():
        return found
    for path in DETECTORS_DIR.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        found.update(CODE_PATTERN.findall(text))
        for m in ENUM_LITERAL.findall(text):
            if m in ENTRIES:
                found.add(m)
    return found


def test_detector_codes_are_in_enum():
    for code in _codes_in_detectors():
        assert code in ENTRIES, f"Detector references unknown code: {code}"
