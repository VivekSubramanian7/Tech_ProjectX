"""Tests for config/scan.yaml loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.scan_config import default_config_path, load_scan_config, repo_root

FIXTURES = Path(__file__).resolve().parent / "fixtures"
FIXTURE_YAML = FIXTURES / "scan.yaml"


def test_default_config_loads_repo_scan_yaml():
    cfg = load_scan_config(default_config_path())
    assert cfg.path.is_dir()
    assert cfg.scope_id == "local-scan-v1"


def test_fixture_resolves_relative_path_against_repo_root():
    cfg = load_scan_config(FIXTURE_YAML)
    assert cfg.path == (repo_root() / "engine" / "tests" / "fixtures").resolve()
    assert cfg.scope_id == "test-scan-fixture"


def test_missing_config_file_raises():
    with pytest.raises(FileNotFoundError, match="scan config not found"):
        load_scan_config(Path("/nonexistent/scan.yaml"))


def test_missing_path_key_raises(tmp_path: Path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("scope_id: only\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing required 'path'"):
        load_scan_config(bad)
