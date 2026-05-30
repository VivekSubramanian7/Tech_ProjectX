"""Determinism test + reusable utility (Story 2.4).

ACs:
- given a fixed corpus, running Tier-1 10x yields byte-identical output
- the check fails loudly on any nondeterminism, reporting the diff

NFR8: reproducibility is a legal property. This is the harness that proves it.
"""
import pytest

from determinism import NondeterminismError, assert_deterministic


def test_deterministic_callable_passes_and_returns_canonical_output():
    def scan():
        return [
            {"code": "EMAIL", "span": [0, 10]},
            {"code": "PASSPORT_NUMBER", "span": [20, 29]},
        ]

    out = assert_deterministic(scan, runs=10)
    assert "EMAIL" in out and "PASSPORT_NUMBER" in out


def test_nondeterministic_callable_raises_with_diff():
    state = {"n": 0}

    def flaky():
        state["n"] += 1
        return {"value": state["n"]}

    with pytest.raises(NondeterminismError) as exc:
        assert_deterministic(flaky, runs=5)
    msg = str(exc.value)
    assert "Nondeterministic" in msg
    assert "run#" in msg  # the unified diff is included


def test_runs_must_be_at_least_two():
    with pytest.raises(ValueError):
        assert_deterministic(lambda: 1, runs=1)


def test_dict_key_order_does_not_cause_false_nondeterminism():
    toggle = {"flip": False}

    def reordered_keys():
        toggle["flip"] = not toggle["flip"]
        # same data, different insertion order on alternate runs
        return {"a": 1, "b": 2} if toggle["flip"] else {"b": 2, "a": 1}

    # canonical serialization (sorted keys) means this is deterministic
    assert_deterministic(reordered_keys, runs=6)


def _stub_tier1_scan():
    """Placeholder for Epic 1's real Tier-1 engine over a fixed corpus.

    Deterministic by construction (sorted findings). Epic 1 replaces this with the
    real engine entry point; the assertion below is the standing NFR8 gate.
    """
    findings = [
        {"file_id": "local:doc1.txt", "code": "EMAIL", "span": [12, 33], "confidence": 0.99},
        {"file_id": "local:doc1.txt", "code": "IBAN", "span": [100, 122], "confidence": 0.99},
    ]
    return sorted(findings, key=lambda f: (f["file_id"], f["span"][0], f["code"]))


def test_tier1_scan_is_deterministic_nfr8():
    assert_deterministic(_stub_tier1_scan, runs=10)
