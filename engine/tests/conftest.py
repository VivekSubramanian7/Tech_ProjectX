from __future__ import annotations

from pathlib import Path

import pytest

from app.repositories import CatalogRepository

ROOT = Path(__file__).resolve().parents[2]
SEED_SQL = ROOT / "data" / "enum_seed.sql"


@pytest.fixture
def repo(tmp_path: Path) -> CatalogRepository:
    r = CatalogRepository(tmp_path / "catalog.sqlite")
    r.init_db(SEED_SQL)
    return r
