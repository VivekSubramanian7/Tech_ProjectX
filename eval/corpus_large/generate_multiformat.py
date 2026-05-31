"""Deterministic generator for the multi-format corpus (.docx + .pdf) — Phase 2.

Run:  python eval/corpus_large/generate_multiformat.py

Reuses the Phase-1 templates (with a *different* master seed, so the documents are
fresh — different people and values than the txt corpus). For each file it writes:
  - the rendered .docx / .pdf            -> data/corpus/{docx,pdf}/<folder>/...
  - a canonical extracted-text sidecar   -> data/corpus/canonical/{docx,pdf}/<folder>/...

Ground truth is ENTITY-LEVEL (native_id, classification_code, occurrence) with no
raw PII value — robust to whatever text-extractor the engine uses. The canonical
sidecar preserves the generator's exact text so span scoring stays possible later.
"""
from __future__ import annotations

import json
import random
import sys
from collections import Counter
from pathlib import Path

import docx as _docx
import faker
import reportlab
import yaml
from faker import Faker

sys.path.insert(0, str(Path(__file__).resolve().parent))
import renderers  # noqa: E402
import templates as T  # noqa: E402

MASTER_SEED = 20260601  # distinct from the txt corpus -> fresh documents
DATASET_VERSION = "1.0.0"

# files per template per format (PII ~240 + decoy ~160 = 400 per format)
PII_PER_TEMPLATE = 16
DECOY_PER_TEMPLATE = 20

_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _DIR.parents[1]
_CORPUS_ROOT = _REPO_ROOT / "data" / "corpus"
_LABELS_FILE = _DIR / "labels_entity.jsonl"
_MANIFEST_FILE = _DIR / "manifest_multiformat.yaml"

PROVENANCE = "synthetic/generator"

_RENDERERS = {"docx": renderers.render_docx, "pdf": renderers.render_pdf}


def _plan() -> list[tuple[T.Template, int]]:
    plan = [(t, PII_PER_TEMPLATE) for t in T.PII_TEMPLATES]
    plan += [(t, DECOY_PER_TEMPLATE) for t in T.DECOY_TEMPLATES]
    return plan


def _clean(fmt: str) -> None:
    for sub in (_CORPUS_ROOT / fmt, _CORPUS_ROOT / "canonical" / fmt):
        if sub.exists():
            for old in sorted(sub.rglob("*")):
                if old.is_file():
                    old.unlink()


def generate() -> dict:
    Faker.seed(MASTER_SEED)
    fkr = Faker("de_DE")
    rng = random.Random(MASTER_SEED)

    for fmt in _RENDERERS:
        _clean(fmt)

    label_rows: list[dict] = []
    category_counts: Counter[str] = Counter()
    format_files: Counter[str] = Counter()
    pii_file_count = 0

    # generate all docx first, then all pdf, off one continuous stream -> distinct content
    for fmt, render in _RENDERERS.items():
        ext = fmt
        for tmpl, count in _plan():
            for i in range(count):
                b = T.DocBuilder()
                tmpl.fn(b, fkr, rng)
                content = b.build()

                native_id = f"{fmt}/{tmpl.folder}/{tmpl.name}_{i:04d}.{ext}"
                render(content, _CORPUS_ROOT / native_id)

                # canonical extracted-text sidecar (exact generator text)
                canon_id = f"canonical/{fmt}/{tmpl.folder}/{tmpl.name}_{i:04d}.txt"
                canon_path = _CORPUS_ROOT / canon_id
                canon_path.parent.mkdir(parents=True, exist_ok=True)
                canon_path.write_text(content, encoding="utf-8")

                format_files[fmt] += 1
                if b.labels:
                    pii_file_count += 1
                for occ, (code, _s, _e) in enumerate(b.labels):
                    category_counts[code] += 1
                    label_rows.append(
                        {
                            "native_id": native_id,
                            "classification_code": code,
                            "modality": "text",
                            "occurrence": occ,
                            "provenance": PROVENANCE,
                            "file_format": fmt,
                        }
                    )

    _write_labels(label_rows)
    _write_manifest(label_rows, category_counts, format_files, pii_file_count)

    total_files = sum(format_files.values())
    return {
        "files": total_files,
        "by_format": dict(format_files),
        "pii_files": pii_file_count,
        "decoy_files": total_files - pii_file_count,
        "entity_labels": len(label_rows),
        "categories": dict(sorted(category_counts.items())),
    }


def _write_labels(rows: list[dict]) -> None:
    with _LABELS_FILE.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_manifest(rows, category_counts, format_files, pii_file_count) -> None:
    total_files = sum(format_files.values())
    manifest = {
        "dataset": "bosch-gdpr-corpus-multiformat",
        "version": DATASET_VERSION,
        "description": (
            "Multi-format (.docx/.pdf) labeled evaluation corpus for the GDPR scan "
            "engine. Entity-level ground truth (no raw PII), with a canonical "
            "extracted-text sidecar per file. Regenerate with "
            "eval/corpus_large/generate_multiformat.py."
        ),
        "granularity": "entity",
        "provenance": {
            "generator": "eval/corpus_large/generate_multiformat.py",
            "master_seed": MASTER_SEED,
            "faker_version": faker.VERSION,
            "faker_locale": "de_DE",
            "python_docx_version": _docx.__version__,
            "reportlab_version": reportlab.Version,
            "annotation": PROVENANCE,
        },
        "counts": {
            "files": total_files,
            "by_format": dict(format_files),
            "pii_files": pii_file_count,
            "decoy_files": total_files - pii_file_count,
            "entity_labels": len(rows),
        },
        "distribution": {
            "by_format": dict(format_files),
            "by_category": dict(sorted(category_counts.items())),
        },
        "target_size": {"files": 800},
    }
    _MANIFEST_FILE.write_text(
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def main() -> None:
    s = generate()
    print(f"Generated {s['files']} files {s['by_format']} "
          f"({s['pii_files']} with PII, {s['decoy_files']} decoys)")
    print(f"Entity labels: {s['entity_labels']}")
    for code, n in s["categories"].items():
        print(f"  {code:28s} {n}")


if __name__ == "__main__":
    main()
