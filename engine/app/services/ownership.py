"""MVP owner attribution from path prefix mapping."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OwnershipResult:
    owner_user_id: str | None
    resolution_method: str
    unresolved: bool = False


class OwnershipResolver:
    def __init__(self, mapping: dict[str, str] | None = None) -> None:
        self._prefix_to_owner = mapping or {}

    @classmethod
    def from_json_file(cls, path: Path) -> OwnershipResolver:
        if not path.is_file():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(data)

    def resolve(self, file_path: str) -> OwnershipResult:
        normalized = file_path.replace("\\", "/")
        for prefix, owner in sorted(self._prefix_to_owner.items(), key=lambda x: -len(x[0])):
            if normalized.startswith(prefix) or f"/{prefix}" in normalized:
                return OwnershipResult(
                    owner_user_id=owner,
                    resolution_method="path_prefix",
                )
        logger.warning("Unresolved owner for path: %s", file_path)
        return OwnershipResult(
            owner_user_id=None,
            resolution_method="unresolved",
            unresolved=True,
        )
