"""End-to-end scan flow: text + image, delta, tier-2."""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

from app.repositories import CatalogRepository
from app.services.scan_orchestrator import ScanOrchestrator

ROOT = Path(__file__).resolve().parents[3]
SEED = ROOT / "data" / "enum_seed.sql"
OWNERS = ROOT / "data" / "mock_owners.json"
TEXT_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _png_with_detect(label: str) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    w, h = 64, 64
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    row = b"\x00" + (b"\xff\x00\x00" * w)
    raw = row * h
    idat = zlib.compress(raw)
    parts = [
        b"\x89PNG\r\n\x1a\n",
        chunk(b"IHDR", ihdr),
        chunk(b"IDAT", idat),
        chunk(b"tEXt", f"gdpr-detect\0{label}".encode("latin-1")),
        chunk(b"IEND", b""),
    ]
    return b"".join(parts)


def _orch(tmp_path: Path) -> ScanOrchestrator:
    repo = CatalogRepository(tmp_path / "catalog.sqlite")
    repo.init_db(SEED)
    return ScanOrchestrator(repo, ownership_map_path=OWNERS)


def test_e2e_full_scan_text_and_image(tmp_path: Path):
    scan_dir = tmp_path / "corpus"
    scan_dir.mkdir()
    (scan_dir / "contact.txt").write_text("Email: e2e@example.com\n", encoding="utf-8")
    (scan_dir / "photo.png").write_bytes(_png_with_detect("FACE:0.91"))

    orch = _orch(tmp_path)
    result = orch.run_scan(scan_dir, mode="full")

    assert result["files_scanned"] == 2
    codes = {f["code"] for f in result["findings"]}
    assert "EMAIL" in codes
    assert "FACE" in codes

    with orch.repo.connect() as conn:
        assert orch.repo.count_catalog(conn) == 2
        rows = orch.repo.list_findings(conn)
        assert len(rows) >= 2


def test_e2e_delta_after_mixed_scan(tmp_path: Path):
    scan_dir = tmp_path / "corpus"
    scan_dir.mkdir()
    txt = scan_dir / "a.txt"
    txt.write_text("Email: one@test.com\n", encoding="utf-8")
    (scan_dir / "pic.png").write_bytes(_png_with_detect("LICENSE_PLATE:0.87"))

    orch = _orch(tmp_path)
    orch.run_scan(scan_dir, mode="full")

    txt.write_text("Email: changed@test.com\n", encoding="utf-8")
    delta = orch.run_scan(scan_dir, mode="delta")

    assert delta["files_processed"] == 1
    assert delta["files_skipped"] >= 1


def test_e2e_tier2_updates_catalog(tmp_path: Path, monkeypatch):
    scan_dir = tmp_path / "corpus"
    scan_dir.mkdir()
    (scan_dir / "ids.txt").write_text(
        "Passport: X12345678\nEmail: low@test.com\n",
        encoding="utf-8",
    )

    def always_escalate(_self, _risk, _conf):
        return True

    monkeypatch.setattr(
        "app.services.escalation_policy.EscalationPolicy.should_escalate",
        always_escalate,
    )

    orch = _orch(tmp_path)
    result = orch.run_scan(scan_dir, mode="full", tier2=True)
    assert result.get("tier2_applied", 0) >= 1

    with orch.repo.connect() as conn:
        tier2_rows = conn.execute("SELECT tier FROM finding WHERE tier = 2").fetchall()
        assert tier2_rows
