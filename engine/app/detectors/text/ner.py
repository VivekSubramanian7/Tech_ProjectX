"""Tier-1 NER text detectors (rule-based MVP; spaCy optional via slow tests)."""

from __future__ import annotations

import re

from app.config import DETECTOR_VERSION
from app.detectors.base import Detection, TextSpan, mask_value
from app.enums import MVP_TEXT_CODES

# German-oriented heuristics for CI without large model downloads.
PERSON_RE = re.compile(
    r"\b(?:Herr|Frau|Dr\.)\s+([A-ZÄÖÜ][a-zäöüß]+(?:\s+[A-ZÄÖÜ][a-zäöüß]+)+)\b"
)
ADDRESS_RE = re.compile(
    r"\b([A-ZÄÖÜ][a-zäöüß]+(?:straße|str\.|weg|platz)\s+\d+[a-z]?,\s*\d{5}\s+[A-ZÄÖÜ][a-zäöüß]+)\b",
    re.IGNORECASE,
)
BILLING_ADDRESS_RE = re.compile(
    r"\b(?:Billing|Shipping|Rechnungs|Liefer)(?:\s+address)?[:\s]+([^\n]{10,120})",
    re.IGNORECASE,
)
TRAVEL_RE = re.compile(
    r"\d{4}-\d{2}-\d{2}\s+[A-ZÄÖÜa-zäöüß]+(?:\s*->\s*[A-ZÄÖÜa-zäöüß]+)+[^\n]*",
)

NER_MODEL_VERSION = "rules-de-0.1.0"


class NerDetector:
    detector_version = DETECTOR_VERSION
    model_version = NER_MODEL_VERSION

    def __init__(self, use_spacy: bool = False) -> None:
        self._nlp = None
        if use_spacy:
            try:
                import spacy

                self._nlp = spacy.load("de_core_news_lg")
                self.model_version = f"de_core_news_lg-{spacy.__version__}"
            except Exception:
                self._nlp = None

    def detect(self, text: str, base_offset: int = 0) -> list[Detection]:
        if self._nlp is not None:
            return self._detect_spacy(text, base_offset)
        return self._detect_rules(text, base_offset)

    def detect_batch(self, segments: list[tuple[str, int]]) -> list[Detection]:
        """Process multiple segments (rules path concatenates; spacy uses nlp.pipe)."""
        if self._nlp is not None:
            texts = [t for t, _ in segments]
            out: list[Detection] = []
            for doc, (_, base) in zip(self._nlp.pipe(texts, batch_size=8), segments):
                for ent in doc.ents:
                    code = _map_spacy_label(ent.label_)
                    if code and code in MVP_TEXT_CODES:
                        out.append(
                            Detection(
                                classification_code=code,
                                span=TextSpan(
                                    start=base + ent.start_char,
                                    end=base + ent.end_char,
                                ),
                                confidence_score=0.85,
                                masked_snippet=mask_value(ent.text),
                                detector_version=self.detector_version,
                                model_version=self.model_version,
                            )
                        )
            return out
        out = []
        for text, base in segments:
            out.extend(self._detect_rules(text, base))
        return out

    def _detect_spacy(self, text: str, base_offset: int) -> list[Detection]:
        return self.detect_batch([(text, base_offset)])

    def _detect_rules(self, text: str, base_offset: int) -> list[Detection]:
        out: list[Detection] = []
        for m in PERSON_RE.finditer(text):
            out.append(
                Detection(
                    classification_code="PERSON_NAME",
                    span=TextSpan(start=base_offset + m.start(1), end=base_offset + m.end(1)),
                    confidence_score=0.8,
                    masked_snippet=mask_value(m.group(1)),
                    detector_version=self.detector_version,
                    model_version=self.model_version,
                )
            )
        for m in ADDRESS_RE.finditer(text):
            out.append(
                Detection(
                    classification_code="HOME_ADDRESS",
                    span=TextSpan(start=base_offset + m.start(1), end=base_offset + m.end(1)),
                    confidence_score=0.8,
                    masked_snippet=mask_value(m.group(1)),
                    detector_version=self.detector_version,
                    model_version=self.model_version,
                )
            )
        for m in BILLING_ADDRESS_RE.finditer(text):
            out.append(
                Detection(
                    classification_code="BILLING_SHIPPING_ADDRESS",
                    span=TextSpan(start=base_offset + m.start(1), end=base_offset + m.end(1)),
                    confidence_score=0.78,
                    masked_snippet=mask_value(m.group(1)),
                    detector_version=self.detector_version,
                    model_version=self.model_version,
                )
            )
        for m in TRAVEL_RE.finditer(text):
            out.append(
                Detection(
                    classification_code="TRAVEL_HISTORY",
                    span=TextSpan(start=base_offset + m.start(), end=base_offset + m.end()),
                    confidence_score=0.82,
                    masked_snippet=mask_value(m.group(0)),
                    detector_version=self.detector_version,
                    model_version=self.model_version,
                )
            )
        return out


def _map_spacy_label(label: str) -> str | None:
    return {
        "PER": "PERSON_NAME",
        "LOC": "HOME_ADDRESS",
        "GPE": "HOME_ADDRESS",
    }.get(label)
