"""Image pipeline — decode once, batch (Story 3.2)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.detectors.image._png import DecodedImage, decode_image_once

MODEL_INPUT = (640, 640)


@dataclass
class PipelineItem:
    path: Path
    decoded: DecodedImage | None = None


class ImagePipeline:
    def __init__(self, *, batch_size: int = 8) -> None:
        self.batch_size = batch_size

    def run(self, paths: list[Path]) -> list[PipelineItem]:
        items = [PipelineItem(path=p) for p in paths]
        for i in range(0, len(items), self.batch_size):
            batch = items[i : i + self.batch_size]
            for item in batch:
                item.decoded = decode_image_once(item.path)
                _letterbox(item.decoded)
        return items


def _letterbox(decoded: DecodedImage) -> None:
    """Resize metadata hook — models consume MODEL_INPUT dimensions."""
    _ = MODEL_INPUT
    _ = decoded
