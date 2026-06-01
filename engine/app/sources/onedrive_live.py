"""Live OneDrive FileSource backed by Microsoft Graph (app-only).

Implements the same FileSource + duck-typed delta contract as the fixture
OneDriveGraphSource so the scan orchestrator routes them identically.

Change-dict contract expected by _run_graph_delta_source:
    {"item_id": str, "change_type": "created"|"modified"|"deleted", "name": str}
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, BinaryIO, Iterator

from app.sources.base import FileRef, FileSource
from app.sources.graph_client import GraphClient

logger = logging.getLogger(__name__)

_FOLDER_FACET = "folder"


def _parse_mtime(dt_str: str | None) -> float:
    if not dt_str:
        return 0.0
    try:
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00")).timestamp()
    except (ValueError, AttributeError):
        return 0.0


class LiveOneDriveGraphSource(FileSource):
    """FileSource that enumerates and downloads files from a real OneDrive drive."""

    def __init__(self, drive_id: str, client: GraphClient | None = None) -> None:
        self._drive_id = drive_id
        self._client = client or GraphClient()
        self._delta_token: str = ""
        # item metadata cache: native_id → {id, name, size, mtime}
        self._items: dict[str, dict[str, Any]] = {}

    # ── FileSource interface ───────────────────────────────────────────────────

    def iter_files(self) -> Iterator[FileRef]:
        """Full enumeration via /root/delta with no prior token."""
        items, delta_token = self._client.iter_delta(self._drive_id, token=None)
        self._delta_token = delta_token
        for item in items:
            if _FOLDER_FACET in item:
                continue
            ref = self._ref_from_item(item)
            if ref:
                self._items[item["id"]] = item
                yield ref

    def open(self, ref: FileRef) -> BinaryIO:
        data = self._client.download(self._drive_id, ref.native_id)
        return BytesIO(data)

    # ── Delta contract (duck-typed, matches OneDriveGraphSource fixture) ───────

    def initial_delta_token(self) -> str:
        return self._delta_token

    def changes_since(self, token: str) -> tuple[list[dict[str, Any]], str]:
        """Return (change_dicts, new_delta_token) since the given token."""
        items, new_token = self._client.iter_delta(self._drive_id, token=token)
        changes: list[dict[str, Any]] = []
        for item in items:
            item_id = item.get("id", "")
            name = item.get("name", item_id)
            if item.get("deleted"):
                changes.append({"item_id": item_id, "change_type": "deleted", "name": name})
                self._items.pop(item_id, None)
            elif item_id in self._items:
                changes.append({"item_id": item_id, "change_type": "modified", "name": name})
                self._items[item_id] = item
            else:
                changes.append({"item_id": item_id, "change_type": "created", "name": name})
                self._items[item_id] = item
        return changes, new_token

    def ref_for_item(self, item_id: str) -> FileRef | None:
        item = self._items.get(item_id)
        if item is None:
            try:
                item = self._client.get_item(self._drive_id, item_id)
                self._items[item_id] = item
            except Exception:
                return None
        return self._ref_from_item(item)

    # ── Internal ───────────────────────────────────────────────────────────────

    def _ref_from_item(self, item: dict[str, Any]) -> FileRef | None:
        item_id = item.get("id")
        if not item_id or _FOLDER_FACET in item:
            return None
        name = item.get("name", item_id)
        return FileRef(
            source_type="onedrive",
            scope_id=self._drive_id,
            native_id=item_id,
            path=f"onedrive://{self._drive_id}/{name}",
            size=int(item.get("size", 0)),
            mtime=_parse_mtime(item.get("lastModifiedDateTime")),
        )
