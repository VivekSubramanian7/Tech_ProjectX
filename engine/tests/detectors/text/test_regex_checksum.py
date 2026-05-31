import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "eval"))
from determinism import assert_deterministic

from app.detectors.text.regex_checksum import RegexChecksumDetector, _de_steuer_valid
from app.enums import MVP_TEXT_CODES

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


def test_steuer_fixture_passes_checksum():
    assert _de_steuer_valid("76095742719")


def test_detects_email_iban_steuer():
    text = (FIXTURES / "german_ids.txt").read_text(encoding="utf-8")
    dets = RegexChecksumDetector().detect(text)
    codes = {d.classification_code for d in dets}
    assert "IBAN" in codes
    assert "DE_STEUER_ID" in codes
    for d in dets:
        assert "•" in d.masked_snippet
        assert d.classification_code in MVP_TEXT_CODES


def test_invalid_luhn_pan_rejected():
    text = (FIXTURES / "invalid_luhn_pan.txt").read_text(encoding="utf-8")
    dets = [d for d in RegexChecksumDetector().detect(text) if d.classification_code == "CREDIT_CARD_NUMBER"]
    assert dets == []


def test_tier1_regex_is_deterministic():
    text = (FIXTURES / "tiny.txt").read_text(encoding="utf-8")

    def run():
        return [
            (d.classification_code, d.span.start, d.span.end, d.masked_snippet)
            for d in RegexChecksumDetector().detect(text)
        ]

    assert_deterministic(run, runs=10)
