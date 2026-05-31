"""Entity-level recall & false-positive harness (Story 2.2).

Scores engine `Finding`s against ground-truth `Label`s at the ENTITY level (not
per-file), broken down by PII category and modality, with top-severity (Critical)
recall gated separately so easy wins can't mask catastrophic misses (NFR6/7/9).

A finding MATCHES a label iff: same file_id, same classification_code, and the
locations overlap (text spans overlap, or image bboxes have IoU >= threshold).
Matching is one-to-one (greedy): each label is matched by at most one finding and
vice-versa. Unmatched labels are false negatives; unmatched findings are false
positives.

Definitions:
- recall          = matched_labels / total_labels
- false_pos_rate  = unmatched_findings / total_findings
"""
from __future__ import annotations

from dataclasses import dataclass

from contracts import BBox, Finding, Label, Location, Span
from enum_ref import TOP_SEVERITY, risk_weight


@dataclass(frozen=True)
class EvalReport:
    overall_recall: float
    false_positive_rate: float
    recall_by_category: dict[str, float]
    recall_by_modality: dict[str, float]
    recall_by_severity: dict[str, float]
    top_severity_recall: float | None
    matched: int
    missed: int
    false_positives: int
    total_labels: int
    total_findings: int


def _spans_overlap(a: Span, b: Span) -> bool:
    return a.start < b.end and b.start < a.end


def _iou(a: BBox, b: BBox) -> float:
    ax2, ay2 = a.x + a.w, a.y + a.h
    bx2, by2 = b.x + b.w, b.y + b.h
    inter_w = max(0, min(ax2, bx2) - max(a.x, b.x))
    inter_h = max(0, min(ay2, by2) - max(a.y, b.y))
    inter = inter_w * inter_h
    if inter == 0:
        return 0.0
    union = a.w * a.h + b.w * b.h - inter
    return inter / union


def _locations_match(a: Location, b: Location, iou_threshold: float) -> bool:
    if isinstance(a, Span) and isinstance(b, Span):
        return _spans_overlap(a, b)
    if isinstance(a, BBox) and isinstance(b, BBox):
        return _iou(a, b) >= iou_threshold
    return False


def _matches(finding: Finding, label: Label, iou_threshold: float) -> bool:
    return (
        finding.file_id == label.file_id
        and finding.classification_code == label.classification_code
        and _locations_match(finding.location, label.location, iou_threshold)
    )


def _ratio(num: int, den: int) -> float | None:
    return num / den if den else None


def match(
    findings: list[Finding], labels: list[Label], *, iou_threshold: float = 0.5
) -> tuple[set[int], set[int]]:
    """Greedy one-to-one match of findings to labels.

    Returns (matched_label_indices, used_finding_indices). A finding index in the
    used set is a true positive; one not in it is a false positive.
    """
    used_findings: set[int] = set()
    matched_label_idxs: set[int] = set()
    for li, label in enumerate(labels):
        for fi, finding in enumerate(findings):
            if fi in used_findings:
                continue
            if _matches(finding, label, iou_threshold):
                used_findings.add(fi)
                matched_label_idxs.add(li)
                break
    return matched_label_idxs, used_findings


def evaluate(
    findings: list[Finding], labels: list[Label], *, iou_threshold: float = 0.5
) -> EvalReport:
    """Score findings against ground-truth labels at entity level."""
    matched_label_idxs, used_findings = match(findings, labels, iou_threshold=iou_threshold)

    matched = len(matched_label_idxs)
    total_labels = len(labels)
    total_findings = len(findings)
    false_positives = total_findings - len(used_findings)

    def recall_over(idxs: list[int]) -> float | None:
        if not idxs:
            return None
        hit = sum(1 for i in idxs if i in matched_label_idxs)
        return hit / len(idxs)

    # Group label indices by category, modality, severity.
    by_cat: dict[str, list[int]] = {}
    by_mod: dict[str, list[int]] = {}
    by_sev: dict[str, list[int]] = {}
    for li, label in enumerate(labels):
        by_cat.setdefault(label.classification_code, []).append(li)
        by_mod.setdefault(label.modality, []).append(li)
        by_sev.setdefault(risk_weight(label.classification_code), []).append(li)

    recall_by_category = {k: recall_over(v) for k, v in by_cat.items()}
    recall_by_modality = {k: recall_over(v) for k, v in by_mod.items()}
    recall_by_severity = {k: recall_over(v) for k, v in by_sev.items()}

    return EvalReport(
        overall_recall=_ratio(matched, total_labels) if total_labels else 1.0,
        false_positive_rate=_ratio(false_positives, total_findings) if total_findings else 0.0,
        recall_by_category=recall_by_category,
        recall_by_modality=recall_by_modality,
        recall_by_severity=recall_by_severity,
        top_severity_recall=recall_by_severity.get(TOP_SEVERITY),
        matched=matched,
        missed=total_labels - matched,
        false_positives=false_positives,
        total_labels=total_labels,
        total_findings=total_findings,
    )


def format_report(report: EvalReport) -> str:
    lines = [
        "=== Eval report (entity-level) ===",
        f"Overall recall:        {report.overall_recall:.1%}  ({report.matched}/{report.total_labels} labels)",
        f"False positive rate:   {report.false_positive_rate:.1%}  ({report.false_positives}/{report.total_findings} findings)",
        f"Top-severity recall:   {_fmt_optional_pct(report.top_severity_recall)}",
        "",
        "Recall by modality:",
    ]
    for mod, val in sorted(report.recall_by_modality.items()):
        lines.append(f"  {mod}: {_fmt_optional_pct(val)}")
    lines.extend(["", "Recall by category:"])
    for cat, val in sorted(report.recall_by_category.items()):
        lines.append(f"  {cat}: {_fmt_optional_pct(val)}")
    return "\n".join(lines)


def _fmt_optional_pct(val: float | None) -> str:
    return "n/a" if val is None else f"{val:.1%}"


def main(argv: list[str] | None = None) -> int:
    import argparse
    import json
    import sys
    from pathlib import Path

    from calibration import calibrate
    from collect_findings import collect_findings
    from labeled_set import load_labeled_set

    parser = argparse.ArgumentParser(description="Run Tier-1 engine on eval corpus and score KPIs.")
    parser.add_argument(
        "--corpus",
        type=Path,
        default=None,
        help="Corpus root (default: data/samples)",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text report")
    parser.add_argument("--calibration", action="store_true", help="Also print confidence calibration curve")
    args = parser.parse_args(argv)

    labels = load_labeled_set()

    try:
        findings = collect_findings(args.corpus)
    except ImportError as exc:
        print(f"Engine not available: {exc}", file=sys.stderr)
        return 1
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    report = evaluate(findings, labels)

    if args.json:
        payload = {
            "overall_recall": report.overall_recall,
            "false_positive_rate": report.false_positive_rate,
            "top_severity_recall": report.top_severity_recall,
            "recall_by_category": report.recall_by_category,
            "recall_by_modality": report.recall_by_modality,
            "matched": report.matched,
            "missed": report.missed,
            "false_positives": report.false_positives,
            "total_labels": report.total_labels,
            "total_findings": report.total_findings,
        }
        print(json.dumps(payload, indent=2))
    else:
        print(format_report(report))
        if args.calibration:
            curve = calibrate(findings, labels)
            print("\n=== Calibration ===")
            for b in curve.bins:
                prec = "n/a" if b.precision is None else f"{b.precision:.1%}"
                print(
                    f"  [{b.lower:.1f},{b.upper:.1f}): n={b.count} tp={b.true_positives} precision={prec}"
                )
            if curve.gaps:
                print("Gaps:", "; ".join(curve.gaps))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
