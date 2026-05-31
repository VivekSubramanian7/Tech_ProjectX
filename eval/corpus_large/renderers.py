"""Render canonical document text into `.docx` and `.pdf`.

The generator builds each document as plain canonical text (the same DocBuilder
used for the txt corpus). These renderers wrap that text in real Office/PDF
containers so the corpus exercises the engine's `.docx`/`.pdf` extraction path.

Reproducibility: both renderers are put into invariant/fixed-timestamp mode so
repeated runs are as deterministic as the formats allow. The legally-relevant
artifacts — the entity labels and the canonical-text sidecar — are byte-stable
regardless; the binaries are faithful containers around that text.
"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path

import reportlab.rl_config as _rl_config

# fixed IDs / dates -> reproducible PDFs (no wall-clock creation date)
_rl_config.invariant = 1

from docx import Document  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.units import mm  # noqa: E402
from reportlab.pdfgen import canvas  # noqa: E402

# fixed metadata timestamp for docx core properties
_FIXED_TS = _dt.datetime(2026, 5, 31, 0, 0, 0)


def render_docx(text: str, path: Path) -> None:
    """Write `text` to a .docx, one paragraph per line."""
    doc = Document()
    for line in text.split("\n"):
        doc.add_paragraph(line)
    props = doc.core_properties
    props.created = _FIXED_TS
    props.modified = _FIXED_TS
    props.author = "gdpr-eval-generator"
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(path))


def render_pdf(text: str, path: Path) -> None:
    """Write `text` to a single- or multi-page A4 PDF, one line per text line."""
    path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(path), pagesize=A4)
    c.setTitle("GDPR eval document")
    c.setAuthor("gdpr-eval-generator")
    width, height = A4
    left = 20 * mm
    top = height - 20 * mm
    line_h = 6 * mm
    bottom = 20 * mm
    y = top
    c.setFont("Helvetica", 10)
    for line in text.split("\n"):
        if y < bottom:
            c.showPage()
            c.setFont("Helvetica", 10)
            y = top
        # Latin-1 is reportlab's base encoding for the built-in Helvetica font;
        # replace anything outside it so umlauts/ß never crash the render.
        safe = line.encode("latin-1", "replace").decode("latin-1")
        c.drawString(left, y, safe)
        y -= line_h
    c.showPage()
    c.save()
