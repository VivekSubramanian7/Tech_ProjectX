# Design — Large Labeled Text Corpus (1,200+ files)

**Date:** 2026-05-31
**Status:** Approved
**Author:** Vivek + Claude

## Goal

Produce a realistic, labeled evaluation corpus of **1,000+ files** for the Bosch
GDPR scan engine, representing real-world German corporate documents. Phase 1
focuses on **`.txt`** with byte-exact character-span ground truth. The architecture
is designed so `.docx` and `.pdf` plug in later (Phase 2) without re-labeling.

This is a **new, separate** dataset. The existing hand-curated seed set at
`eval/labeled_set/` (15 labels, 12 files) is left completely untouched and remains
the fast golden set for unit tests.

## Non-goals

- Replacing or modifying the existing `eval/labeled_set/` seed set or its tests.
- Image-modality PII (SIGNATURE / FACE / LICENSE_PLATE) — those need real images,
  out of scope for a text corpus.
- LLM-generated prose. Generation is 100% deterministic (legal reproducibility).

## Decisions (locked)

| Topic | Decision |
|---|---|
| Relationship to seed set | New separate large corpus; reuse harness `contracts` + `enum_ref` |
| Generation method | Deterministic, seeded Python generator (slot-injection, spans correct by construction) |
| Fake-data source | `Faker` (`de_DE` locale), seeded; custom providers for checksummed DE IDs / PAN / passport |
| PII / decoy mix | ~60% files contain PII, ~40% PII-free decoys (with hard near-misses) |
| Phase 1 scale | ~1,200 `.txt` files |
| Multi-format | Phased: txt now (exact spans); docx/pdf later (entity-level labels) |

## Layout & artifacts

```
data/corpus/text/                 # the generated .txt files
  hr/ finance/ email/ legal/ support/ travel/ logs/ config/ product/ marketing/
eval/corpus_large/
  __init__.py                     # loader (mirrors eval/labeled_set loader, reuses contracts)
  generate.py                     # deterministic seeded generator (CLI entry)
  templates.py                    # document templates: ordered blocks + typed PII slots
  pii_providers.py                # checksummed DE IDs / PAN / passport Faker lacks
  labels.jsonl                    # one label/line: native_id, classification_code, modality, span, provenance
  manifest.yaml                   # dataset meta, master seed, distribution, target_size
docs/superpowers/specs/2026-05-31-large-labeled-text-corpus-design.md
```

- `native_id` = path relative to `data/corpus/` (e.g. `text/hr/record_0042.txt`),
  matching the existing native_id→file convention. The loader resolves files
  against a `data/corpus/` root (parallel to `eval_corpus_root()` for samples).
- Reuses `contracts.Span` / `contracts.Label` and the 20 `enum_ref.ENUM` codes.
  **HARD RULE:** the corpus must not emit a classification absent from the enum.
- `provenance` = `"synthetic/generator"`; master seed recorded in `manifest.yaml`
  for audit / reproducibility.

## Document mix & PII coverage

~1,200 files, ~60% PII / ~40% decoy, across German corporate document types:

| Folder | Examples | Typical PII |
|---|---|---|
| `hr/` | employee records, onboarding, leave requests, payroll stubs | name, employee-ID, address, SVNR, Steuer-ID, ID card |
| `finance/` | invoices, expense reports, purchase orders | IBAN, PAN, billing address, name |
| `email/` | internal threads, customer/vendor mail | email, phone, name |
| `legal/` | employment contracts, NDAs, consent forms | name, passport, address |
| `support/` | customer tickets, complaint logs | name, email, phone |
| `travel/` | trip notes, travel expense | travel history, passport, name |
| `logs/` `config/` | server/access logs, app configs | IP, username (sparse); many are decoys |
| `product/` `marketing/` | release notes, specs, FAQs | decoys (no PII) |

**Coverage = the 17 text-modality enum codes:** PERSON_NAME, USERNAME, EMAIL,
PHONE_NUMBER, FAX_NUMBER, HOME_ADDRESS, BILLING_SHIPPING_ADDRESS, PASSPORT_NUMBER,
DE_PERSONALAUSWEIS, DRIVERS_LICENSE_NUMBER, TRAVEL_HISTORY, IBAN,
CREDIT_CARD_NUMBER, IP_ADDRESS, EMPLOYEE_ID, DE_SOZIALVERSICHERUNGSNR, DE_STEUER_ID.
(Image codes SIGNATURE / FACE / LICENSE_PLATE excluded.) Every code gets a
meaningful count; the manifest distribution is enforced by tests.

**Hard negatives in decoys:** order numbers, SKUs, version strings, ticket IDs,
ISO dates, money amounts, German postal codes, IBAN-shaped reference numbers, and
invalid-checksum ID variants — so false positives are exercised, not just absent.

## Generation architecture

**Slot-injection (spans correct by construction):**

1. A template is an ordered list of blocks; some blocks contain typed **PII slots**.
2. The generator appends pieces to a text buffer. When it appends a PII value, it
   records `Span(start=len_before, end=len_after)` and a `Label`.
3. No post-hoc searching → no collision / substring errors. Spans are exact.

**Determinism:** a single master seed (in `manifest.yaml`) seeds `Faker.seed()` and
`random.seed()`. Re-running `generate.py` yields **byte-identical** files and labels.

**Checksums:**
- IBAN, credit-card PAN → Faker (already mod-97 / Luhn valid).
- DE Steuer-ID (11-digit check), Sozialversicherungsnr, Personalausweis, German
  passport → custom providers implementing real check-digit algorithms.
- Invalid-checksum variants seeded into decoys as near-misses.

## Multi-format (Phase 2, designed-for now)

The generator builds an **abstract document** (ordered blocks + typed slots) handed
to a **renderer**:

- **Phase 1 — `txt` renderer:** exact character spans. Fully labeled, harness-scorable.
- **Phase 2 — `docx` (python-docx) / `pdf` (reportlab) renderers:** same abstract
  docs rendered to those formats. Ground truth is **entity-level** (`native_id`,
  `classification_code`, occurrence) — robust against text-extractor variance and
  consistent with the existing entity-level recall harness (Story 2.2). Optional
  canonical extracted-text sidecar enables span scoring later.

New dev dependencies: `Faker` (Phase 1); `python-docx` + `reportlab` (Phase 2).

## Testing

- **Loader test:** every label has a known enum code + valid span + provenance
  (mirrors `eval/test_labeled_set.py`).
- **Corpus alignment:** for every text label, the file exists and the snippet at
  `[start:end)` is non-empty and shape-matches the code (mirrors
  `eval/test_corpus_alignment.py`).
- **Determinism:** regenerating with the manifest seed reproduces identical
  `labels.jsonl` and file bytes (hash check).
- **Distribution:** manifest `by_modality` / `by_category` sums equal label counts;
  every enum text code is represented above a floor.
- **Scale:** corpus has ≥ 1,000 files; PII/decoy ratio within tolerance of 60/40.

## Reproducibility / audit

- Master seed + Faker/lib versions recorded in `manifest.yaml`.
- `provenance = synthetic/generator` on every label.
- Generation is a single idempotent command: `python eval/corpus_large/generate.py`.
