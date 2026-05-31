"""Tests for the entity-level recall & false-positive harness (Story 2.2).

ACs:
- report entity-level recall and FP rate, broken down by PII category and modality
- top-severity (Critical) recall reported and gated separately from aggregate recall
"""
import math

from contracts import BBox, EntityLabel, Finding, Label, Span
from run_eval import evaluate, evaluate_entity


def _label(code, modality="text", loc=None, file_id="f1"):
    loc = loc or (Span(0, 10) if modality == "text" else BBox(0, 0, 10, 10))
    return Label(
        file_id=file_id,
        native_id="test.txt",
        classification_code=code,
        modality=modality,
        location=loc,
        provenance="test",
    )


def _finding(code, modality="text", loc=None, conf=0.9, risk="Medium", file_id="f1"):
    loc = loc or (Span(0, 10) if modality == "text" else BBox(0, 0, 10, 10))
    return Finding(file_id=file_id, classification_code=code, modality=modality,
                   location=loc, confidence_score=conf, risk_weight=risk)


def test_perfect_detection_gives_full_recall_and_zero_fp():
    labels = [_label("EMAIL"), _label("PASSPORT_NUMBER", loc=Span(20, 29))]
    findings = [_finding("EMAIL"), _finding("PASSPORT_NUMBER", loc=Span(20, 29))]
    report = evaluate(findings, labels)
    assert report.overall_recall == 1.0
    assert report.false_positive_rate == 0.0


def test_missed_label_lowers_recall():
    labels = [_label("EMAIL"), _label("PASSPORT_NUMBER", loc=Span(20, 29))]
    findings = [_finding("EMAIL")]  # passport missed
    report = evaluate(findings, labels)
    assert report.overall_recall == 0.5


def test_false_positive_counts_against_fp_rate():
    labels = [_label("EMAIL")]
    findings = [_finding("EMAIL"), _finding("PHONE_NUMBER", loc=Span(50, 60))]
    report = evaluate(findings, labels)
    assert report.overall_recall == 1.0
    # 1 of 2 findings has no matching label
    assert report.false_positive_rate == 0.5


def test_overlapping_span_counts_as_match_disjoint_does_not():
    labels = [_label("EMAIL", loc=Span(10, 20))]
    overlap = evaluate([_finding("EMAIL", loc=Span(15, 25))], labels)
    disjoint = evaluate([_finding("EMAIL", loc=Span(30, 40))], labels)
    assert overlap.overall_recall == 1.0
    assert disjoint.overall_recall == 0.0
    assert disjoint.false_positive_rate == 1.0  # the finding matched nothing


def test_wrong_code_at_same_location_is_not_a_match():
    labels = [_label("PASSPORT_NUMBER", loc=Span(0, 9))]
    findings = [_finding("DRIVERS_LICENSE_NUMBER", loc=Span(0, 9))]
    report = evaluate(findings, labels)
    assert report.overall_recall == 0.0
    assert report.false_positive_rate == 1.0


def test_image_bbox_matches_on_iou_threshold():
    labels = [_label("FACE", modality="image", loc=BBox(0, 0, 100, 100))]
    hit = evaluate([_finding("FACE", modality="image", loc=BBox(5, 5, 100, 100))], labels)
    miss = evaluate([_finding("FACE", modality="image", loc=BBox(500, 500, 50, 50))], labels)
    assert hit.overall_recall == 1.0
    assert miss.overall_recall == 0.0


def test_recall_broken_down_by_category_and_modality():
    labels = [
        _label("EMAIL"),
        _label("PASSPORT_NUMBER", loc=Span(20, 29)),
        _label("FACE", modality="image"),
    ]
    findings = [_finding("EMAIL")]  # only EMAIL detected
    report = evaluate(findings, labels)
    assert report.recall_by_category["EMAIL"] == 1.0
    assert report.recall_by_category["PASSPORT_NUMBER"] == 0.0
    assert report.recall_by_modality["text"] == 0.5
    assert report.recall_by_modality["image"] == 0.0


def _elabel(code, file_id="f1", occ=0, fmt="docx"):
    return EntityLabel(
        file_id=file_id,
        native_id="x." + fmt,
        classification_code=code,
        modality="text",
        occurrence=occ,
        provenance="test",
        file_format=fmt,
    )


def test_entity_perfect_match_ignores_location():
    labels = [_elabel("EMAIL"), _elabel("PASSPORT_NUMBER")]
    # findings at arbitrary spans — location is irrelevant in entity mode
    findings = [_finding("EMAIL", loc=Span(999, 1004)), _finding("PASSPORT_NUMBER", loc=Span(7, 9))]
    report = evaluate_entity(findings, labels)
    assert report.overall_recall == 1.0
    assert report.false_positive_rate == 0.0


def test_entity_missed_label_lowers_recall():
    labels = [_elabel("EMAIL"), _elabel("PASSPORT_NUMBER")]
    report = evaluate_entity([_finding("EMAIL")], labels)
    assert report.overall_recall == 0.5


def test_entity_wrong_file_is_not_a_match():
    labels = [_elabel("EMAIL", file_id="A")]
    report = evaluate_entity([_finding("EMAIL", file_id="B")], labels)
    assert report.overall_recall == 0.0
    assert report.false_positive_rate == 1.0


def test_entity_multiplicity_is_one_to_one():
    # two PERSON_NAME entities in the same file -> need two findings to fully recall
    labels = [_elabel("PERSON_NAME", occ=0), _elabel("PERSON_NAME", occ=1)]
    one = evaluate_entity([_finding("PERSON_NAME")], labels)
    two = evaluate_entity([_finding("PERSON_NAME"), _finding("PERSON_NAME")], labels)
    assert one.overall_recall == 0.5
    assert two.overall_recall == 1.0


def test_entity_recall_broken_down_by_format():
    labels = [_elabel("EMAIL", fmt="docx"), _elabel("EMAIL", file_id="f2", fmt="pdf")]
    findings = [_finding("EMAIL", file_id="f1")]  # only the docx one detected
    report = evaluate_entity(findings, labels)
    assert report.recall_by_modality["docx"] == 1.0
    assert report.recall_by_modality["pdf"] == 0.0


def test_top_severity_recall_gated_separately():
    # Aggregate recall is high (2/3) but a Critical (passport) is missed →
    # top-severity recall must reflect the catastrophic miss, not be masked.
    labels = [
        _label("EMAIL"),                                  # Medium
        _label("IP_ADDRESS", loc=Span(20, 30)),           # Low
        _label("PASSPORT_NUMBER", loc=Span(40, 49)),      # Critical
    ]
    findings = [_finding("EMAIL"), _finding("IP_ADDRESS", loc=Span(20, 30))]
    report = evaluate(findings, labels)
    assert math.isclose(report.overall_recall, 2 / 3)
    assert report.top_severity_recall == 0.0  # the Critical entity was missed
