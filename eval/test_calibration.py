"""Tests for the confidence calibration curve (Story 2.3).

ACs:
- output precision per confidence bin
- if calibration is insufficient (too few samples in a bin), report the gap
  explicitly rather than hiding it
"""
from contracts import Finding, Label, Span
from calibration import calibrate


def _label(code, start, file_id="f1"):
    return Label(file_id=file_id, classification_code=code, modality="text",
                 location=Span(start, start + 9), provenance="test")


def _finding(code, start, conf, file_id="f1"):
    return Finding(file_id=file_id, classification_code=code, modality="text",
                   location=Span(start, start + 9), confidence_score=conf,
                   risk_weight="Medium")


def test_confidence_lands_in_expected_decile_bin():
    labels = [_label("EMAIL", 0)]
    findings = [_finding("EMAIL", 0, conf=0.95)]
    curve = calibrate(findings, labels, n_bins=10, min_samples=1)
    top = curve.bins[-1]
    assert (top.lower, top.upper) == (0.9, 1.0)
    assert top.count == 1


def test_all_true_positives_give_precision_one():
    labels = [_label("EMAIL", 0), _label("PHONE_NUMBER", 20)]
    findings = [_finding("EMAIL", 0, 0.92), _finding("PHONE_NUMBER", 20, 0.95)]
    curve = calibrate(findings, labels, min_samples=1)
    top = curve.bins[-1]
    assert top.true_positives == 2
    assert top.precision == 1.0


def test_false_positive_lowers_bin_precision():
    labels = [_label("EMAIL", 0)]
    # one TP + one FP (no matching label) both in the top bin
    findings = [_finding("EMAIL", 0, 0.95), _finding("PHONE_NUMBER", 99, 0.95)]
    curve = calibrate(findings, labels, min_samples=1)
    top = curve.bins[-1]
    assert top.count == 2
    assert top.true_positives == 1
    assert top.precision == 0.5


def test_undersampled_bin_reported_as_gap_with_no_precision():
    labels = [_label("EMAIL", 0)]
    findings = [_finding("EMAIL", 0, 0.95)]  # only 1 sample, min_samples=5
    curve = calibrate(findings, labels, n_bins=10, min_samples=5)
    top = curve.bins[-1]
    assert top.count == 1
    assert top.precision is None       # not enough data to claim a precision
    assert top.sufficient is False
    assert curve.sufficient is False
    assert any("0.9" in g for g in curve.gaps)


def test_well_sampled_bin_is_sufficient():
    labels = [_label("EMAIL", i * 10) for i in range(5)]
    findings = [_finding("EMAIL", i * 10, 0.95) for i in range(5)]
    curve = calibrate(findings, labels, n_bins=10, min_samples=5)
    top = curve.bins[-1]
    assert top.count == 5
    assert top.precision == 1.0
    assert top.sufficient is True
    assert curve.sufficient is True
    assert curve.gaps == []
