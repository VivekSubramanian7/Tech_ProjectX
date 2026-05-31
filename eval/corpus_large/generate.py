"""Deterministic generator for the large labeled text corpus.

Run:  python eval/corpus_large/generate.py

Writes ~1,200 realistic German `.txt` documents under `data/corpus/text/`, plus
`labels.jsonl` (exact character spans) and `manifest.yaml` next to this module.
Everything is driven by a single master seed, so re-running reproduces byte-identical
files and labels — the reproducibility-as-legal-property requirement from the PRD.
"""
from __future__ import annotations

import json
import random
import sys
from collections import Counter
from pathlib import Path

import faker
import yaml
from faker import Faker

# work whether imported as a package submodule or run as a loose script
sys.path.insert(0, str(Path(__file__).resolve().parent))
import templates as T  # noqa: E402

MASTER_SEED = 20260531
DATASET_VERSION = "1.0.0"

# files generated per template (PII templates ~720, decoys ~480 => ~1,200 total)
PII_PER_TEMPLATE = 48
DECOY_PER_TEMPLATE = 60

_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _DIR.parents[1]
_CORPUS_ROOT = _REPO_ROOT / "data" / "corpus"
_TEXT_ROOT = _CORPUS_ROOT / "text"
_LABELS_FILE = _DIR / "labels.jsonl"
_MANIFEST_FILE = _DIR / "manifest.yaml"

PROVENANCE = "synthetic/generator"


def _plan() -> list[tuple[T.Template, int]]:
    """Deterministic (template, count) plan — PII templates first, then decoys."""
    plan = [(t, PII_PER_TEMPLATE) for t in T.PII_TEMPLATES]
    plan += [(t, DECOY_PER_TEMPLATE) for t in T.DECOY_TEMPLATES]
    return plan


def generate() -> dict:
    """Generate the corpus + labels + manifest. Returns a summary dict."""
    Faker.seed(MASTER_SEED)
    fkr = Faker("de_DE")
    rng = random.Random(MASTER_SEED)

    # clean any previous output so regeneration is exact (no stale files)
    if _TEXT_ROOT.exists():
        for old in sorted(_TEXT_ROOT.rglob("*.txt")):
            old.unlink()

    label_rows: list[dict] = []
    category_counts: Counter[str] = Counter()
    file_count = 0
    pii_file_count = 0

    for tmpl, count in _plan():
        out_dir = _TEXT_ROOT / tmpl.folder
        out_dir.mkdir(parents=True, exist_ok=True)
        for i in range(count):
            b = T.DocBuilder()
            tmpl.fn(b, fkr, rng)
            content = b.build()
            native_id = f"text/{tmpl.folder}/{tmpl.name}_{i:04d}.txt"
            (_CORPUS_ROOT / native_id).write_text(content, encoding="utf-8")
            file_count += 1
            if b.labels:
                pii_file_count += 1
            for code, start, end in b.labels:
                category_counts[code] += 1
                label_rows.append(
                    {
                        "native_id": native_id,
                        "classification_code": code,
                        "modality": "text",
                        "location": {"type": "span", "start": start, "end": end},
                        "provenance": PROVENANCE,
                    }
                )

    _write_labels(label_rows)
    _write_manifest(label_rows, category_counts, file_count, pii_file_count)

    return {
        "files": file_count,
        "pii_files": pii_file_count,
        "decoy_files": file_count - pii_file_count,
        "labels": len(label_rows),
        "categories": dict(sorted(category_counts.items())),
    }


def _write_labels(rows: list[dict]) -> None:
    with _LABELS_FILE.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_manifest(
    rows: list[dict],
    category_counts: Counter[str],
    file_count: int,
    pii_file_count: int,
) -> None:
    manifest = {
        "dataset": "bosch-gdpr-corpus-large",
        "version": DATASET_VERSION,
        "description": (
            "Large synthetic labeled evaluation corpus for the GDPR scan engine. "
            "Realistic German corporate .txt documents with span-level ground truth. "
            "Deterministically generated; regenerate with eval/corpus_large/generate.py."
        ),
        "modality": "text",
        "provenance": {
            "generator": "eval/corpus_large/generate.py",
            "master_seed": MASTER_SEED,
            "faker_version": faker.VERSION,
            "faker_locale": "de_DE",
            "annotation": PROVENANCE,
        },
        "counts": {
            "files": file_count,
            "pii_files": pii_file_count,
            "decoy_files": file_count - pii_file_count,
            "labels": len(rows),
        },
        "distribution": {
            "by_modality": {"text": len(rows)},
            "by_category": dict(sorted(category_counts.items())),
        },
        "target_size": {"files": 1000, "text_entities": 1000},
    }
    _MANIFEST_FILE.write_text(
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def main() -> None:
    summary = generate()
    print(f"Generated {summary['files']} files "
          f"({summary['pii_files']} with PII, {summary['decoy_files']} decoys)")
    print(f"Labels: {summary['labels']}")
    print("By category:")
    for code, n in summary["categories"].items():
        print(f"  {code:28s} {n}")


if __name__ == "__main__":
    main()
