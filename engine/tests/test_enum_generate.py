from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from app.enums import ENTRIES, lookup

ROOT = Path(__file__).resolve().parents[2]


def test_generate_creates_enums_and_seed():
    subprocess.run(
        [sys.executable, str(ROOT / "enum" / "generate.py")],
        check=True,
        cwd=str(ROOT),
    )
    assert (ROOT / "engine" / "app" / "enums.py").is_file()
    assert (ROOT / "data" / "enum_seed.sql").is_file()
    assert len(ENTRIES) == 37


def test_lookup_email():
    entry = lookup("EMAIL")
    assert entry.display_label == "Email address"
    assert entry.risk_weight == "Medium"


def test_mvp_text_codes_include_core_detectors():
    from app.enums import MVP_TEXT_CODES

    for code in ("EMAIL", "DE_STEUER_ID", "IBAN", "PASSPORT_NUMBER"):
        assert code in MVP_TEXT_CODES
