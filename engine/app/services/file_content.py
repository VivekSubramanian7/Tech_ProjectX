"""Resolve and read file bytes for owner document preview (no raw PII in errors)."""

from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path
from typing import Any

from app.repositories import CatalogRepository
from app.scan_config import load_scan_config, resolve_scan_source
from app.detectors.text.extract import extract_docx_bytes, extract_pptx_bytes

TEXT_SUFFIXES = {
    ".txt",
    ".md",
    ".csv",
    ".json",
    ".xml",
    ".html",
    ".htm",
    ".log",
    ".yaml",
    ".yml",
    ".py",
    ".java",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".sql",
    ".ini",
    ".cfg",
    ".env",
    ".rtf",
}

MAX_PREVIEW_BYTES = 512_000
# Images must be read in full (truncation corrupts the file); cap higher.
IMAGE_MAX_BYTES = 8_000_000

# Browser-renderable image formats → MIME type for a base64 data URL.
IMAGE_MIME_BY_SUFFIX = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


def _user_owns_file(repo: CatalogRepository, conn: Any, *, file_id: str, owner_user_id: str) -> bool:
    row = conn.execute(
        """
        SELECT 1 FROM finding
        WHERE file_id = ? AND owner_user_id = ?
        LIMIT 1
        """,
        (file_id, owner_user_id),
    ).fetchone()
    if row is not None:
        return True
    own = conn.execute(
        "SELECT owner_user_id FROM file_ownership WHERE file_id = ?",
        (file_id,),
    ).fetchone()
    return own is not None and own["owner_user_id"] == owner_user_id


def _read_bytes_for_path(
    catalog_path: str, source_id: str | None, max_bytes: int = MAX_PREVIEW_BYTES
) -> bytes | None:
    path = catalog_path.replace("\\", "/")

    if path.startswith("onedrive://"):
        try:
            cfg = load_scan_config()
            source = resolve_scan_source(cfg)
            from app.sources.onedrive_graph import OneDriveGraphSource

            if not isinstance(source, OneDriveGraphSource):
                return None
            # onedrive://{drive_id}/{name}
            parts = path.split("/", 3)
            if len(parts) < 4:
                return None
            drive_id = parts[2]
            name = parts[3]
            for item_id, item in source._items.items():
                if source._drive_id == drive_id and item.get("name") == name:
                    return base64.b64decode(item.get("content_b64", ""))
            return None
        except Exception:
            return None

    candidate = Path(catalog_path)
    if candidate.is_file():
        return candidate.read_bytes()[:max_bytes]

    try:
        cfg = load_scan_config()
        root = resolve_scan_source(cfg)
        if isinstance(root, Path):
            joined = (root / catalog_path).resolve()
            if joined.is_file():
                return joined.read_bytes()[:max_bytes]
    except Exception:
        pass

    return None


def load_owner_file_preview(
    repo: CatalogRepository,
    conn: Any,
    *,
    file_id: str,
    owner_user_id: str,
) -> dict[str, Any]:
    if not _user_owns_file(repo, conn, file_id=file_id, owner_user_id=owner_user_id):
        raise PermissionError("not_owner")

    row = repo.get_catalog_entry(conn, file_id)
    if row is None:
        raise FileNotFoundError(file_id)

    catalog_path = row["path"]
    suffix = Path(catalog_path.split("/")[-1]).suffix.lower()

    result: dict[str, Any] = {
        "file_id": file_id,
        "file_path": catalog_path,
        "renderable": False,
        "media_type": None,
        "content": None,
        "unsupported_reason": None,
    }

    # Images: return the full file as a base64 data URL so the owner can view it
    # (they own the file; the finding stores only a bbox, never raw PII).
    if suffix in IMAGE_MIME_BY_SUFFIX:
        raw_img = _read_bytes_for_path(catalog_path, row["source_id"], max_bytes=IMAGE_MAX_BYTES)
        if raw_img is None:
            result["unsupported_reason"] = "file_not_available"
            return result
        mime = IMAGE_MIME_BY_SUFFIX[suffix]
        encoded = base64.b64encode(raw_img).decode("ascii")
        result["renderable"] = True
        result["media_type"] = mime
        result["content"] = f"data:{mime};base64,{encoded}"
        return result

    raw = _read_bytes_for_path(catalog_path, row["source_id"])

    if raw is None:
        result["unsupported_reason"] = "file_not_available"
        return result

    if suffix in TEXT_SUFFIXES or suffix == "":
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            result["unsupported_reason"] = "binary_file"
            return result
        result["renderable"] = True
        result["media_type"] = "text/plain"
        result["content"] = text[:MAX_PREVIEW_BYTES]
        return result

    if suffix == ".docx":
        try:
            text = extract_docx_bytes(raw)
        except Exception:
            result["unsupported_reason"] = "extract_failed"
            return result
        result["renderable"] = True
        result["media_type"] = (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        result["content"] = text[:MAX_PREVIEW_BYTES]
        return result

    if suffix == ".pptx":
        try:
            text = extract_pptx_bytes(raw)
        except Exception:
            result["unsupported_reason"] = "extract_failed"
            return result
        result["renderable"] = True
        result["media_type"] = (
            "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        )
        result["content"] = text[:MAX_PREVIEW_BYTES]
        return result

    result["unsupported_reason"] = "unsupported_type"
    return result
