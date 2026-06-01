from pathlib import Path

from app.detectors.text.regex_checksum import RegexChecksumDetector
from app.repositories import CatalogRepository
from app.services.finding_write import write_detection
from app.services.ownership import OwnershipResolver
from fastapi.testclient import TestClient

from app.main import app
from office_fixtures import minimal_docx, minimal_pptx


def _seed_owner_finding(
    repo: CatalogRepository,
    *,
    owner: str = "user-alpha",
    tmp_path=None,
) -> int:
    text = "Contact: secret@example.com"
    det = RegexChecksumDetector().detect(text)[0]
    ownership = OwnershipResolver({"team-alpha/": owner})

    if tmp_path is not None:
        report = tmp_path / "team-alpha" / "report.txt"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(text, encoding="utf-8")
        catalog_path = str(report)
    else:
        catalog_path = "team-alpha/report.txt"

    with repo.connect() as conn:
        repo.upsert_catalog(
            conn,
            file_id="f-owner",
            source_id="local",
            path=catalog_path,
            content_hash="h1",
            size=len(text),
            mtime=1.0,
            ruleset_version="0.1.0",
            scan_status="complete",
        )
        finding_id = write_detection(
            repo,
            conn,
            file_id="f-owner",
            det=det,
            page=None,
            ownership=ownership,
            file_path="team-alpha/report.txt",
        )
        conn.commit()
    return finding_id


def test_owner_file_content_preview(tmp_path, monkeypatch):
    db = tmp_path / "catalog.sqlite"
    repo = CatalogRepository(db)
    repo.init_db()
    _seed_owner_finding(repo, tmp_path=tmp_path)

    monkeypatch.setattr("app.api.findings._repo", repo)
    client = TestClient(app)
    headers = {"X-Acting-User": "user-alpha"}

    res = client.get("/me/files/f-owner/content", headers=headers)
    assert res.status_code == 200
    body = res.json()["data"]
    assert body["renderable"] is True
    assert "secret@example.com" in body["content"]
    assert "secret@example.com" not in str(
        client.get("/me/findings", headers=headers).json()
    )


def _seed_office_preview(
    repo: CatalogRepository,
    *,
    tmp_path,
    file_id: str,
    catalog_path: Path,
    file_bytes: bytes,
    scan_text: str,
) -> None:
    det = RegexChecksumDetector().detect(scan_text)[0]
    ownership = OwnershipResolver({"team-alpha/": "user-alpha"})
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    catalog_path.write_bytes(file_bytes)

    with repo.connect() as conn:
        repo.upsert_catalog(
            conn,
            file_id=file_id,
            source_id="local",
            path=str(catalog_path),
            content_hash="h-office",
            size=len(file_bytes),
            mtime=1.0,
            ruleset_version="0.1.0",
            scan_status="complete",
        )
        write_detection(
            repo,
            conn,
            file_id=file_id,
            det=det,
            page=None,
            ownership=ownership,
            file_path=str(catalog_path.relative_to(tmp_path)),
        )
        conn.commit()


def test_owner_file_content_preview_docx(tmp_path, monkeypatch):
    db = tmp_path / "catalog.sqlite"
    repo = CatalogRepository(db)
    repo.init_db()
    email = "docx@example.com"
    path = tmp_path / "team-alpha" / "memo.docx"
    _seed_office_preview(
        repo,
        tmp_path=tmp_path,
        file_id="f-docx",
        catalog_path=path,
        file_bytes=minimal_docx(f"Contact: {email}"),
        scan_text=f"Contact: {email}",
    )

    monkeypatch.setattr("app.api.findings._repo", repo)
    client = TestClient(app)
    headers = {"X-Acting-User": "user-alpha"}

    res = client.get("/me/files/f-docx/content", headers=headers)
    assert res.status_code == 200
    body = res.json()["data"]
    assert body["renderable"] is True
    assert "wordprocessingml" in body["media_type"]
    assert email in body["content"]


def test_owner_file_content_preview_pptx(tmp_path, monkeypatch):
    db = tmp_path / "catalog.sqlite"
    repo = CatalogRepository(db)
    repo.init_db()
    email = "slide@example.com"
    path = tmp_path / "team-alpha" / "deck.pptx"
    _seed_office_preview(
        repo,
        tmp_path=tmp_path,
        file_id="f-pptx",
        catalog_path=path,
        file_bytes=minimal_pptx([f"Contact: {email}"]),
        scan_text=f"Contact: {email}",
    )

    monkeypatch.setattr("app.api.findings._repo", repo)
    client = TestClient(app)
    headers = {"X-Acting-User": "user-alpha"}

    res = client.get("/me/files/f-pptx/content", headers=headers)
    assert res.status_code == 200
    body = res.json()["data"]
    assert body["renderable"] is True
    assert "presentationml" in body["media_type"]
    assert email in body["content"]
    assert "--- Slide 1 ---" in body["content"]


def test_owner_queue_and_actions(tmp_path, monkeypatch):
    db = tmp_path / "catalog.sqlite"
    repo = CatalogRepository(db)
    repo.init_db()
    finding_id = _seed_owner_finding(repo, tmp_path=tmp_path)

    monkeypatch.setattr("app.api.findings._repo", repo)
    client = TestClient(app)
    headers = {"X-Acting-User": "user-alpha"}

    listed = client.get("/me/findings", headers=headers)
    assert listed.status_code == 200
    body = listed.json()
    assert body["meta"]["open_count"] == 1
    assert body["data"][0]["display_label"] == "Email address"
    assert "secret@example.com" not in str(body)

    kept = client.post(
        f"/findings/{finding_id}/keep",
        headers=headers,
        json={"reason": "Needed for vendor billing"},
    )
    assert kept.status_code == 200
    assert kept.json()["data"]["resolution_status"] == "kept"

    empty = client.get("/me/findings", headers=headers)
    assert empty.json()["meta"]["open_count"] == 0


def test_owner_rbac_denies_other_user(tmp_path, monkeypatch):
    db = tmp_path / "catalog.sqlite"
    repo = CatalogRepository(db)
    repo.init_db()
    finding_id = _seed_owner_finding(repo, owner="user-beta")

    monkeypatch.setattr("app.api.findings._repo", repo)
    client = TestClient(app)

    denied = client.post(
        f"/findings/{finding_id}/delete",
        headers={"X-Acting-User": "user-alpha"},
    )
    assert denied.status_code == 403
