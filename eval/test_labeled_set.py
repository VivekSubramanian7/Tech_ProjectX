"""Tests for the labeled evaluation set + loader (Story 2.1).

ACs:
- every label has an enum code + char span (text) or bbox (image) + provenance
- the manifest reports inter-annotator agreement (Cohen's kappa >= 0.8) and a
  category/modality distribution
"""
from contracts import BBox, Span
from enum_ref import ENUM
from eval_config import EVAL_SCOPE_ID, eval_file_id
from labeled_set import load_labeled_set, load_manifest


def test_labeled_set_is_non_empty():
    labels = load_labeled_set()
    assert len(labels) > 0


def test_every_label_uses_a_known_enum_code():
    for label in load_labeled_set():
        assert label.classification_code in ENUM, label.classification_code


def test_location_type_matches_modality():
    for label in load_labeled_set():
        if label.modality == "text":
            assert isinstance(label.location, Span)
            assert label.location.end > label.location.start
        elif label.modality == "image":
            assert isinstance(label.location, BBox)
            assert label.location.w > 0 and label.location.h > 0
        else:
            raise AssertionError(f"unknown modality {label.modality!r}")


def test_every_label_has_provenance():
    for label in load_labeled_set():
        assert label.provenance


def test_manifest_reports_kappa_at_or_above_threshold():
    manifest = load_manifest()
    assert manifest["inter_annotator_kappa"] >= 0.8


def test_manifest_distribution_matches_label_counts():
    labels = load_labeled_set()
    dist = load_manifest()["distribution"]
    assert sum(dist["by_modality"].values()) == len(labels)
    assert sum(dist["by_category"].values()) == len(labels)


def test_set_is_text_only():
    modalities = {label.modality for label in load_labeled_set()}
    assert modalities == {"text"}


def test_file_id_is_stable_sha256_hex():
    expected = eval_file_id("onboarding_email.txt")
    assert len(expected) == 64
    assert all(c in "0123456789abcdef" for c in expected)
    labels = load_labeled_set()
    onboarding = next(
        l for l in labels
        if l.classification_code == "EMAIL" and l.file_id == expected
    )
    assert onboarding.file_id == eval_file_id("onboarding_email.txt")


def test_eval_scope_id_is_fixed():
    assert EVAL_SCOPE_ID == "gdpr-eval-samples-v1"
