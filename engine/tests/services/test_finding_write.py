from pathlib import Path

from app.detectors.base import Detection, TextSpan
from app.detectors.text.regex_checksum import RegexChecksumDetector
from app.repositories import CatalogRepository
from app.services.finding_write import write_detection
from app.services.ownership import OwnershipResolver

ROOT = Path(__file__).resolve().parents[3]


def test_written_finding_has_no_raw_pii(repo, tmp_path):
    text = "Email: secret@example.com"
    det = RegexChecksumDetector().detect(text)[0]
    ownership = OwnershipResolver({"": "user-default"})

    with repo.connect() as conn:
        repo.upsert_catalog(
            conn,
            file_id="f1",
            source_id="local",
            path="/x.txt",
            content_hash="h",
            size=1,
            mtime=1.0,
            ruleset_version="0.1.0",
            scan_status="complete",
        )
        write_detection(
            repo,
            conn,
            file_id="f1",
            det=det,
            page=None,
            ownership=ownership,
            file_path="/team-alpha/doc.txt",
        )
        conn.commit()

    with repo.connect() as conn:
        row = repo.list_findings(conn, "f1")[0]
        blob = str(row)
        assert "secret@example.com" not in blob
        assert row["masked_snippet"]
        audit = conn.execute(
            "SELECT detector_version, model_version, prompt_hash FROM audit_log"
        ).fetchone()
        assert audit["detector_version"]
        assert audit["model_version"] is None
        assert audit["prompt_hash"] is None
