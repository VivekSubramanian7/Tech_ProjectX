"""Tests for the shared eval-harness contracts (frozen dataclasses)."""
import dataclasses

import pytest

import contracts


def test_span_holds_char_offsets_and_is_frozen():
    span = contracts.Span(start=3, end=10)
    assert span.start == 3
    assert span.end == 10
    with pytest.raises(dataclasses.FrozenInstanceError):
        span.start = 99  # type: ignore[misc]


def test_bbox_holds_xywh_and_is_frozen():
    box = contracts.BBox(x=1, y=2, w=30, h=40)
    assert (box.x, box.y, box.w, box.h) == (1, 2, 30, 40)
    with pytest.raises(dataclasses.FrozenInstanceError):
        box.x = 0  # type: ignore[misc]


def test_label_carries_span_for_text():
    label = contracts.Label(
        file_id="doc1.txt",
        native_id="doc1.txt",
        classification_code="EMAIL",
        modality="text",
        location=contracts.Span(0, 5),
        provenance="manual-annotation",
    )
    assert label.modality == "text"
    assert isinstance(label.location, contracts.Span)
    assert label.provenance == "manual-annotation"
    with pytest.raises(dataclasses.FrozenInstanceError):
        label.file_id = "x"  # type: ignore[misc]


def test_label_carries_bbox_for_image():
    label = contracts.Label(
        file_id="img1.png",
        native_id="img1.png",
        classification_code="FACE",
        modality="image",
        location=contracts.BBox(10, 20, 30, 40),
        provenance="manual-annotation",
    )
    assert isinstance(label.location, contracts.BBox)


def test_finding_shape_for_downstream_stories():
    finding = contracts.Finding(
        file_id="doc1.txt",
        classification_code="EMAIL",
        modality="text",
        location=contracts.Span(0, 5),
        confidence_score=0.91,
        risk_weight="Medium",
    )
    assert finding.confidence_score == pytest.approx(0.91)
    assert finding.risk_weight == "Medium"
    with pytest.raises(dataclasses.FrozenInstanceError):
        finding.confidence_score = 0.1  # type: ignore[misc]
