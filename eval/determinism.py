"""Reusable determinism check (Story 2.4).

Runs a callable N times and asserts every run produces byte-identical output after
canonical serialization. On any divergence it raises loudly with a unified diff.

NFR8: deterministic detectors must produce 100% identical results across repeated
runs — reproducibility is a legal property. Callers should return output in a
canonical order; dict key order is normalized here (sort_keys), so key reordering
alone never registers as nondeterminism.
"""
from __future__ import annotations

import difflib
import json
from typing import Any, Callable


class NondeterminismError(AssertionError):
    """Raised when repeated runs of a supposedly deterministic callable differ."""


def _canonical(output: Any) -> str:
    return json.dumps(output, sort_keys=True, default=str, ensure_ascii=False, indent=2)


def assert_deterministic(run: Callable[[], Any], *, runs: int = 10) -> str:
    """Run `run` `runs` times; assert all outputs are identical.

    Returns the canonical output string on success. Raises NondeterminismError with a
    unified diff on the first divergence.
    """
    if runs < 2:
        raise ValueError("runs must be >= 2 to detect nondeterminism")

    baseline = _canonical(run())
    for i in range(2, runs + 1):
        current = _canonical(run())
        if current != baseline:
            diff = "\n".join(
                difflib.unified_diff(
                    baseline.splitlines(),
                    current.splitlines(),
                    fromfile="run#1",
                    tofile=f"run#{i}",
                    lineterm="",
                )
            )
            raise NondeterminismError(
                f"Nondeterministic output detected on run {i} of {runs}:\n{diff}"
            )
    return baseline
