"""Image decode helpers shared by image detectors."""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DecodedImage:
    width: int
    height: int
    rgb: bytes

    @property
    def shape(self) -> tuple[int, int, int]:
        return (self.height, self.width, 3)

    def tobytes(self) -> bytes:
        return self.rgb


def read_png_text_chunks(data: bytes) -> dict[str, str]:
    """Extract tEXt key/value pairs from a PNG byte stream."""
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return {}
    pos = 8
    out: dict[str, str] = {}
    while pos + 8 <= len(data):
        length = struct.unpack(">I", data[pos : pos + 4])[0]
        tag = data[pos + 4 : pos + 8]
        chunk = data[pos + 8 : pos + 8 + length]
        pos += 12 + length
        if tag == b"tEXt":
            nul = chunk.find(b"\0")
            if nul >= 0:
                key = chunk[:nul].decode("latin-1", errors="replace")
                val = chunk[nul + 1 :].decode("latin-1", errors="replace")
                out[key] = val
        if tag == b"IEND":
            break
    return out


def _decode_png_bytes(data: bytes) -> DecodedImage:
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("not a PNG file")

    pos = 8
    width = height = 0
    idat = b""
    while pos + 8 <= len(data):
        length = struct.unpack(">I", data[pos : pos + 4])[0]
        tag = data[pos + 4 : pos + 8]
        chunk = data[pos + 8 : pos + 8 + length]
        pos += 12 + length
        if tag == b"IHDR" and len(chunk) >= 8:
            width, height = struct.unpack(">II", chunk[:8])
        elif tag == b"IDAT":
            idat += chunk
        elif tag == b"IEND":
            break

    raw = zlib.decompress(idat)
    rgb = bytearray()
    stride = width * 3
    offset = 0
    for _y in range(height):
        offset += 1  # filter byte
        row = raw[offset : offset + stride]
        offset += stride
        rgb.extend(row)

    return DecodedImage(width=width, height=height, rgb=bytes(rgb))


def _decode_with_pillow(path: Path, data: bytes) -> DecodedImage:
    try:
        from PIL import Image
    except ImportError as exc:
        raise ValueError(f"unsupported image format: {path}") from exc

    import io

    img = Image.open(io.BytesIO(data)).convert("RGB")
    width, height = img.size
    return DecodedImage(width=width, height=height, rgb=img.tobytes())


def decode_image_once(path: Path) -> DecodedImage:
    """Decode image once to shared RGB bytes (PNG native; JPEG/WebP via Pillow)."""
    data = path.read_bytes()
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return _decode_png_bytes(data)
    return _decode_with_pillow(path, data)
