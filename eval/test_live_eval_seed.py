"""End-to-end: Tier-1 engine on eval corpus vs labeled seed set (Story 2.2)."""

from __future__ import annotations

import pytest

from collect_findings import collect_findings
from eval_config import eval_file_id
from labeled_set import load_labeled_set
from run_eval import evaluate

# Categories with no Tier-1 detector yet — excluded from minimum-recall checks.
_NO_DETECTOR: frozenset[str] = frozenset()


@pytest.fixture(scope="module")
def findings():
    try:
        return collect_findings()
    except ImportError:
        pytest.skip("engine package not on PYTHONPATH")


def test_live_eval_report_populated(findings):
    labels = load_labeled_set()
    assert len(labels) == 15
    report = evaluate(findings, labels)
    assert report.total_labels == 15
    assert report.total_findings >= 0
    assert 0.0 <= report.overall_recall <= 1.0
    assert 0.0 <= report.false_positive_rate <= 1.0
    assert "text" in report.recall_by_modality


def test_label_file_ids_match_engine_scope(findings):
    labels = load_labeled_set()
    finding_ids = {f.file_id for f in findings}
    for native in {l.native_id for l in labels}:
        assert eval_file_id(native) in finding_ids or native in {
            "license.txt",
            "trip_notes.txt",
        }


def test_detected_categories_include_core_tier1(findings):
    """Plumbing check: regex/NER categories we expect on the seed corpus."""
    labels = load_labeled_set()
    report = evaluate(findings, labels)
    scorable = [c for c in report.recall_by_category if c not in _NO_DETECTOR]
    assert scorable, "no scorable categories"
    hits = [c for c in scorable if (report.recall_by_category.get(c) or 0) > 0]
    assert {"EMAIL", "IP_ADDRESS"} <= set(hits)
