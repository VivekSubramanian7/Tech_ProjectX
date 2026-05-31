"""OneDrive FileSource via Microsoft Graph (Stories 6.1, 6.2)."""

from __future__ import annotations

import base64
import json
from io import BytesIO
from pathlib import Path
from typing import Any, BinaryIO, Iterator

from app.sources.base import FileRef, FileSource


class OneDriveGraphSource(FileSource):
    """Graph-backed source; fixture mode for tests without live OAuth."""

    def __init__(
        self,
        *,
        drive_id: str,
        items: list[dict[str, Any]],
        delta_changes: list[dict[str, Any]] | None = None,
        delta_token: str = "delta-v0",
        delta_token_next: str = "delta-v1",
    ) -> None:
        self._drive_id = drive_id
        self._items = {item["id"]: item for item in items}
        self._delta_changes = delta_changes or []
        self._delta_token = delta_token
        self._delta_token_next = delta_token_next

    @classmethod
    def from_fixture(cls, path: Path) -> OneDriveGraphSource:
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            drive_id=data["drive_id"],
            items=data["items"],
            delta_changes=data.get("delta_changes", []),
            delta_token=data.get("delta_token", "delta-v0"),
            delta_token_next=data.get("delta_token_next", "delta-v1"),
        )

    def iter_files(self) -> Iterator[FileRef]:
        for item_id in sorted(self._items):
            item = self._items[item_id]
            yield FileRef(
                source_type="onedrive",
                scope_id=self._drive_id,
                native_id=item_id,
                path=f"onedrive://{self._drive_id}/{item.get('name', item_id)}",
                size=int(item.get("size", 0)),
                mtime=float(item.get("mtime", 0.0)),
            )

    def ref_for_item(self, item_id: str) -> FileRef | None:
        item = self._items.get(item_id)
        if item is None:
            return None
        return FileRef(
            source_type="onedrive",
            scope_id=self._drive_id,
            native_id=item_id,
            path=f"onedrive://{self._drive_id}/{item.get('name', item_id)}",
            size=int(item.get("size", 0)),
            mtime=float(item.get("mtime", 0.0)),
        )

    def add_item(self, item: dict[str, Any]) -> None:
        """Fixture helper — register an item for delta-created files."""
        self._items[item["id"]] = item

    def open(self, ref: FileRef) -> BinaryIO:
        item = self._items[ref.native_id]
        raw = base64.b64decode(item.get("content_b64", ""))
        stream: BinaryIO = BytesIO(raw)
        return stream

    def initial_delta_token(self) -> str:
        return self._delta_token

    def changes_since(self, token: str) -> tuple[list[dict[str, Any]], str]:
        if token != self._delta_token:
            return [], token
        return self._delta_changes, self._delta_token_next
