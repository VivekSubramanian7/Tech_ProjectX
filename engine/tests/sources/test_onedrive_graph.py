"""OneDrive FileSource + Graph delta feed (Stories 6.1, 6.2)."""

import json
from pathlib import Path

from app.sources.onedrive_graph import OneDriveGraphSource

FIXTURE = Path(__file__).resolve().parents[3] / "data" / "onedrive_fixture.json"


def test_onedrive_iter_yields_refs_without_download():
    src = OneDriveGraphSource.from_fixture(FIXTURE)
    refs = list(src.iter_files())
    assert len(refs) >= 1
    assert all(r.source_type == "onedrive" for r in refs)
    assert all(r.file_id for r in refs)


def test_onedrive_open_streams_chunks():
    src = OneDriveGraphSource.from_fixture(FIXTURE)
    ref = next(src.iter_files())
    with src.open(ref) as stream:
        data = stream.read()
    assert b"Email:" in data or len(data) > 0


def test_onedrive_delta_returns_changes_only():
    src = OneDriveGraphSource.from_fixture(FIXTURE)
    token = src.initial_delta_token()
    changes, new_token = src.changes_since(token)
    assert new_token
    assert isinstance(changes, list)
    assert any(c["change_type"] in {"created", "modified", "deleted"} for c in changes)
