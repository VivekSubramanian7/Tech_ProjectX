from pathlib import Path

from app.repositories import CatalogRepository


def test_repositories_crud(tmp_path: Path):
    root = Path(__file__).resolve().parents[2]
    repo = CatalogRepository(tmp_path / "cat.sqlite")
    repo.init_db(root / "data" / "enum_seed.sql")

    with repo.connect() as conn:
        repo.upsert_catalog(
            conn,
            file_id="abc",
            source_id="local",
            path="/x.txt",
            content_hash="h1",
            size=10,
            mtime=1.0,
            ruleset_version="0.1.0",
            scan_status="complete",
        )
        fid = repo.insert_finding(
            conn,
            file_id="abc",
            classification_code="EMAIL",
            location={"span": [0, 5]},
            masked_snippet="a•••",
            risk_score=2.0,
            confidence_score=0.99,
            detector_version="t1",
        )
        repo.append_audit(
            conn,
            entity_type="finding",
            entity_id=str(fid),
            action="created",
            detector_version="t1",
        )
        conn.commit()

    with repo.connect() as conn:
        assert repo.count_catalog(conn) == 1
        rows = repo.list_findings(conn, "abc")
        assert len(rows) == 1
        audit = conn.execute("SELECT COUNT(*) AS c FROM audit_log").fetchone()
        assert audit["c"] == 1
