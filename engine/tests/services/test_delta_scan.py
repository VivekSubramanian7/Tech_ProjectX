"""Delta scan + ruleset sweep (Stories 5.1, 5.2)."""

import time
from pathlib import Path

from app.repositories import CatalogRepository
from app.services.scan_orchestrator import ScanOrchestrator

ROOT = Path(__file__).resolve().parents[3]
SEED = ROOT / "data" / "enum_seed.sql"
OWNERS = ROOT / "data" / "mock_owners.json"


def _orch(tmp_path: Path) -> ScanOrchestrator:
    repo = CatalogRepository(tmp_path / "catalog.sqlite")
    repo.init_db(SEED)
    return ScanOrchestrator(repo, ownership_map_path=OWNERS)


def test_delta_skips_unchanged_files(tmp_path):
    scan_dir = tmp_path / "docs"
    scan_dir.mkdir()
    f1 = scan_dir / "a.txt"
    f1.write_text("Contact: alice@example.com\n", encoding="utf-8")

    orch = _orch(tmp_path)
    orch.run_full(scan_dir)

    f1.write_text("Contact: alice@example.com\n", encoding="utf-8")
    result = orch.run_delta(scan_dir)

    assert result["files_processed"] == 0
    assert result["files_skipped"] >= 1


def test_delta_processes_only_changed_file(tmp_path):
    scan_dir = tmp_path / "docs"
    scan_dir.mkdir()
    f1 = scan_dir / "a.txt"
    f2 = scan_dir / "b.txt"
    f1.write_text("Email: one@test.com\n", encoding="utf-8")
    f2.write_text("Email: two@test.com\n", encoding="utf-8")

    orch = _orch(tmp_path)
    orch.run_full(scan_dir)

    f2.write_text("Email: changed@test.com\n", encoding="utf-8")
    time.sleep(0.05)
    result = orch.run_delta(scan_dir)

    assert result["files_processed"] == 1
    assert result["files_skipped"] >= 1


def test_delta_removes_deleted_file_from_catalog(tmp_path):
    scan_dir = tmp_path / "docs"
    scan_dir.mkdir()
    f1 = scan_dir / "keep.txt"
    f2 = scan_dir / "gone.txt"
    f1.write_text("Email: keep@test.com\n", encoding="utf-8")
    f2.write_text("Email: gone@test.com\n", encoding="utf-8")

    orch = _orch(tmp_path)
    orch.run_full(scan_dir)
    f2.unlink()

    orch.run_delta(scan_dir)

    with orch.repo.connect() as conn:
        paths = {
            row["path"]
            for row in conn.execute("SELECT path FROM scan_catalog").fetchall()
        }
    assert not any("gone.txt" in p for p in paths)


def test_ruleset_sweep_without_flag_skips_unchanged(tmp_path, monkeypatch):
    scan_dir = tmp_path / "docs"
    scan_dir.mkdir()
    (scan_dir / "a.txt").write_text("Email: x@test.com\n", encoding="utf-8")

    orch = _orch(tmp_path)
    orch.run_full(scan_dir)

    monkeypatch.setattr("app.config.RULESET_VERSION", "0.2.0")
    result = orch.run_delta(scan_dir, reapply_ruleset=False)

    assert result["files_processed"] == 0


def test_ruleset_sweep_with_flag_reprocesses_stale(tmp_path, monkeypatch):
    scan_dir = tmp_path / "docs"
    scan_dir.mkdir()
    (scan_dir / "a.txt").write_text("Email: x@test.com\n", encoding="utf-8")

    orch = _orch(tmp_path)
    orch.run_full(scan_dir)

    monkeypatch.setattr("app.config.RULESET_VERSION", "0.2.0")
    result = orch.run_delta(scan_dir, reapply_ruleset=True)

    assert result["files_processed"] >= 1
