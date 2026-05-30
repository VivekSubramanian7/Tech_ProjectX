"""Confidence calibration curve (Story 2.3).

Bins findings by their confidence score and computes the ACTUAL precision in each
bin (true positives / total in bin), so the escalation thresholds (Epic 4 τ) can be
tuned with data instead of guesses. Where a bin has too few samples to claim a
precision, the gap is reported explicitly rather than hidden (PRD: "produce a
calibration curve, or name the gap explicitly").
"""
from __future__ import annotations

from dataclasses import dataclass

from contracts import Finding, Label
from run_eval import match


@dataclass(frozen=True)
class CalibrationBin:
    lower: float
    upper: float
    count: int
    true_positives: int
    precision: float | None  # None when under-sampled (see `sufficient`)
    sufficient: bool


@dataclass(frozen=True)
class CalibrationCurve:
    bins: list[CalibrationBin]
    min_samples: int
    sufficient: bool       # True only if every populated bin met min_samples
    gaps: list[str]        # human-readable description of under-sampled bins


def calibrate(
    findings: list[Finding],
    labels: list[Label],
    *,
    n_bins: int = 10,
    min_samples: int = 5,
    iou_threshold: float = 0.5,
) -> CalibrationCurve:
    """Bin findings by confidence and report precision (or the gap) per bin."""
    _, used = match(findings, labels, iou_threshold=iou_threshold)

    counts = [0] * n_bins
    true_pos = [0] * n_bins
    for fi, finding in enumerate(findings):
        idx = min(int(finding.confidence_score * n_bins), n_bins - 1)
        idx = max(0, idx)
        counts[idx] += 1
        if fi in used:
            true_pos[idx] += 1

    bins: list[CalibrationBin] = []
    gaps: list[str] = []
    for i in range(n_bins):
        lower, upper = i / n_bins, (i + 1) / n_bins
        count, tp = counts[i], true_pos[i]
        sufficient = count >= min_samples
        precision = (tp / count) if (count and sufficient) else None
        bins.append(CalibrationBin(lower, upper, count, tp, precision, sufficient))
        if 0 < count < min_samples:
            gaps.append(
                f"bin [{lower:.1f},{upper:.1f}): only {count} sample(s) "
                f"(<{min_samples}) — precision not reliable"
            )

    overall_sufficient = bool(findings) and not gaps
    return CalibrationCurve(bins=bins, min_samples=min_samples,
                            sufficient=overall_sufficient, gaps=gaps)
