"""FileSource abstraction — metadata-only iteration, lazy chunked reads."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import BinaryIO, Iterator

from app.identity import file_id as compute_file_id


@dataclass(frozen=True)
class FileRef:
    source_type: str
    scope_id: str
    native_id: str
    path: str
    size: int
    mtime: float

    @property
    def file_id(self) -> str:
        return compute_file_id(self.source_type, self.scope_id, self.native_id)


class FileSource(ABC):
    @abstractmethod
    def iter_files(self) -> Iterator[FileRef]:
        """Yield file metadata without reading contents."""

    @abstractmethod
    def open(self, ref: FileRef) -> BinaryIO:
        """Open a readable binary stream for the file."""
