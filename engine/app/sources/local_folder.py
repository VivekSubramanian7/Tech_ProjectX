"""Local folder FileSource implementation."""

from __future__ import annotations

import mmap
import os
from io import BytesIO
from pathlib import Path
from typing import BinaryIO, Iterator

from app.config import CHUNK_SIZE
from app.sources.base import FileRef, FileSource


class ChunkedReader:
    """BinaryIO wrapper that reads in bounded chunks via mmap."""

    def __init__(self, path: Path, chunk_size: int = CHUNK_SIZE) -> None:
        self._path = path
        self._chunk_size = chunk_size
        self._f = path.open("rb")
        self._mm: mmap.mmap | None = None
        if self._f.seek(0, os.SEEK_END) > 0:
            self._f.seek(0)
            self._mm = mmap.mmap(self._f.fileno(), 0, access=mmap.ACCESS_READ)
        self._pos = 0

    def read(self, size: int = -1) -> bytes:
        if self._mm is None:
            return b""
        if size < 0:
            size = self._chunk_size
        size = min(size, self._chunk_size)
        end = min(self._pos + size, len(self._mm))
        data = self._mm[self._pos : end]
        self._pos = end
        return bytes(data)

    def readall(self) -> bytes:
        chunks: list[bytes] = []
        while True:
            chunk = self.read(self._chunk_size)
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks)

    def close(self) -> None:
        if self._mm is not None:
            self._mm.close()
            self._mm = None
        self._f.close()

    def __enter__(self) -> ChunkedReader:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


class LocalFolderSource(FileSource):
    def __init__(
        self,
        root: Path,
        *,
        source_type: str = "local",
        scope_id: str | None = None,
    ) -> None:
        self._root = root.resolve()
        self._scope_id = scope_id if scope_id is not None else str(self._root)
        self._source_type = source_type

    def iter_files(self) -> Iterator[FileRef]:
        for path in sorted(self._root.rglob("*")):
            if not path.is_file():
                continue
            stat = path.stat()
            native = str(path.relative_to(self._root)).replace("\\", "/")
            yield FileRef(
                source_type=self._source_type,
                scope_id=self._scope_id,
                native_id=native,
                path=str(path),
                size=stat.st_size,
                mtime=stat.st_mtime,
            )

    def open(self, ref: FileRef) -> BinaryIO:
        return ChunkedReader(Path(ref.path))
