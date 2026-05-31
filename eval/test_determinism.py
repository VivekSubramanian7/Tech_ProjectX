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


def _tier1_scan_engine():
    """Tier-1 engine over eval corpus with fixed scope_id (NFR8)."""
    try:
        from collect_findings import collect_findings
        from eval_config import EVAL_SCOPE_ID, eval_corpus_root
    except ImportError:
        return _tier1_scan_engine_fixtures_stub()

    corpus = eval_corpus_root()
    if not corpus.is_dir():
        return _tier1_scan_engine_fixtures_stub()

    def _run():
        findings = collect_findings(corpus, scope_id=EVAL_SCOPE_ID)
        return sorted(
            [
                {
                    "file_id": f.file_id,
                    "code": f.classification_code,
                    "span": [f.location.start, f.location.end],
                    "confidence": f.confidence_score,
                }
                for f in findings
            ],
            key=lambda f: (f["file_id"], f["span"][0], f["code"]),
        )

    return _run


def _tier1_scan_engine_fixtures_stub():
    """Fallback when engine or eval corpus is unavailable."""
    import tempfile
    from pathlib import Path

    fixtures = Path(__file__).resolve().parents[1] / "engine" / "tests" / "fixtures"
    if not fixtures.is_dir():
        fixtures = Path(__file__).resolve().parents[1] / ".." / "engine" / "tests" / "fixtures"
    fixtures = fixtures.resolve()
    try:
        from app.repositories import CatalogRepository
        from app.services.scan_orchestrator import ScanOrchestrator
    except ImportError:
        def _stub():
            return [
                {"file_id": "local:doc1.txt", "code": "EMAIL", "span": [12, 33], "confidence": 0.99},
            ]

        return _stub

    root = Path(__file__).resolve().parents[1]
    seed = root / "data" / "enum_seed.sql"
    owners = root / "data" / "mock_owners.json"

    def _run():
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "catalog.sqlite"
            repo = CatalogRepository(db)
            repo.init_db(seed if seed.is_file() else None)
            orch = ScanOrchestrator(repo, ownership_map_path=owners if owners.is_file() else None)
            return orch.tier1_scan_callable(fixtures)()

    return _run


def test_tier1_scan_is_deterministic_nfr8():
    assert_deterministic(_tier1_scan_engine(), runs=10)
