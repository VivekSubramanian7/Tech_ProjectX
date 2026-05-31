"""Coverage for remaining MVP text detector categories."""

from pathlib import Path

from app.detectors.text.ner import NerDetector
from app.detectors.text.regex_checksum import RegexChecksumDetector

SAMPLES = Path(__file__).resolve().parents[4] / "data" / "samples"


def test_detects_personalausweis_and_drivers_license():
    hr = (SAMPLES / "hr_record.txt").read_text(encoding="utf-8")
    license_text = (SAMPLES / "license.txt").read_text(encoding="utf-8")
    det = RegexChecksumDetector()
    hr_codes = {d.classification_code for d in det.detect(hr)}
    lic_codes = {d.classification_code for d in det.detect(license_text)}
    assert "DE_PERSONALAUSWEIS" in hr_codes
    assert "DRIVERS_LICENSE_NUMBER" in lic_codes


def test_ner_travel_history():
    text = (SAMPLES / "trip_notes.txt").read_text(encoding="utf-8")
    dets = NerDetector(use_spacy=False).detect(text)
    assert any(d.classification_code == "TRAVEL_HISTORY" for d in dets)
