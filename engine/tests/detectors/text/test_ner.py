from pathlib import Path

from app.detectors.text.ner import NerDetector

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


def test_german_name_and_address_detected():
    text = (FIXTURES / "german_ner.txt").read_text(encoding="utf-8")
    dets = NerDetector(use_spacy=False).detect(text)
    codes = {d.classification_code for d in dets}
    assert "PERSON_NAME" in codes
    assert "HOME_ADDRESS" in codes


def test_batch_matches_single_segment_rules():
    text = (FIXTURES / "german_ner.txt").read_text(encoding="utf-8")
    ner = NerDetector(use_spacy=False)
    single = ner.detect(text, 0)
    batch = ner.detect_batch([(text, 0)])
    assert {d.classification_code for d in single} == {d.classification_code for d in batch}
    assert ner.model_version
