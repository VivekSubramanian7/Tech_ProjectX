---
stepsCompleted: [1, 2, 3]
inputDocuments:
  - '_bmad-output/prd.md'
  - '_bmad-output/architecture.md'
  - '_bmad-output/pii-detection-scope.md'
scope: 'SCAN ENGINE domain only (FR1-FR27, NFR1-NFR9). Owner/admin/escalation UI epics deferred.'
storyStyle: 'Self-contained: each story embeds enough context (files, contracts, enum refs, ACs) for an independent subagent to implement without the broader conversation.'
---

# Bosch GDPR Data Discovery (Scan Engine) - Epic Breakdown

## Overview

This document decomposes the **scan engine** slice of the Automated GDPR Compliance platform into
implementable, self-contained stories. Each story carries embedded context (target files, interface
contracts, enum references, acceptance criteria) so an independent subagent can implement it without
the broader design conversation. Sources: PRD (FR1-FR27, NFR1-NFR9), Architecture (scan flow, delta,
modality routing, file identity, streaming/performance, escalation thresholds), pii-detection-scope.md (enum).

## Requirements Inventory

### Functional Requirements (scan domain)

**Data Source Ingestion**
- FR1: The system can ingest files from a local folder source. `[MVP]`
- FR2: The system can ingest files from a user's OneDrive. `[MVP]`
- FR3: The system can ingest files from SharePoint sites. `[Growth]`
- FR4: The system can ingest files from network file shares. `[Growth]`
- FR5: The system can read text documents. `[MVP]`
- FR5a: The system can read images. `[MVP]`
- FR5b: The system can read video. `[Growth]`

**Detection & Classification**
- FR6: The system can detect the canonical Priority-1 personal-data attributes in text. `[MVP]`
- FR7: The system can detect personal data embedded in images via OCR. `[MVP]`
- FR8: The system can detect faces/persons in images. `[MVP]`
- FR9: The system can detect vehicle licence plates in images. `[MVP]`
- FR10: The system can detect signatures in images. `[MVP]`
- FR11: The system can detect the German ID card number. `[MVP]`
- FR11a: The system can detect the German social security number. `[MVP]`
- FR11b: The system can detect the German tax ID. `[MVP]`
- FR12: The system can detect IBANs. `[MVP]`
- FR12a: The system can detect payment card numbers (PAN). `[MVP]`
- FR13: The system can assign each finding a classification from a controlled vocabulary (enum). `[MVP]`
- FR14: The system can escalate low-confidence findings to an AI model for a second-opinion verdict. `[MVP]`
- FR15: The system can detect personal data in video. `[Growth]`
- FR16: The system can detect special-category (Art. 9) data. `[Vision]`

**Scoring & Findings**
- FR17: The system can assign each finding a legal-risk score. `[MVP]`
- FR18: The system can assign each finding a detection-confidence score. `[MVP]`
- FR19: The system can record each finding with location, classification, risk, and confidence — without storing the raw PII value. `[MVP]`
- FR20: The system can present a masked snippet / location pointer for context. `[MVP]`
- FR21: The system can attribute each finding to a responsible data owner. `[MVP]`
- FR22: The system can resolve ownership for shared/orphaned/departed-employee files via a fallback chain. `[Growth]`

**Scan Orchestration**
- FR23: An administrator can trigger a full scan of a configured source. `[MVP]`
- FR24: The system can perform delta scans that re-evaluate only files changed since the last scan. `[MVP]`
- FR25: The system can re-evaluate previously-cleared files when detection rules are updated. `[MVP]`
- FR26: The system can track and report scan progress and completion. `[MVP]`
- FR27: The system can run scans on a recurring schedule. `[Growth]`

### NonFunctional Requirements (scan domain)

- NFR1: Throughput measured as time-to-scan a fixed 1 GB mixed corpus on defined HW (median of 3 runs); delta materially faster than full.
- NFR2: User-facing dashboard actions complete within ~2s. *(UI-facing; out of scan-engine scope, listed for traceability.)*
- NFR3: Tier-2 AI escalation invoked on only a minority of files (target <10% at scale).
- NFR4: Tier-1 runs on commodity CPU (no GPU); measured CPU/RAM-per-GB budget with an Architect-set ceiling.
- NFR5: Heavy Tier-2 inference isolated so it never gates the common (Tier-1) path.
- NFR6: Entity-level recall on P1 ≥90% (text) / ≥80% (image) at PoC vs labeled eval set; engine recall-biased.
- NFR7: False-positive rate ≤25% at PoC (human review filters cheaply).
- NFR8: Deterministic detectors produce 100% identical results across repeated runs (reproducibility — legal property).
- NFR9: Top-severity (Art. 9) recall gated separately at a higher bar than P1; never below the P1 floor.

### Additional Requirements (from Architecture — binding on scan stories)

- **Monorepo scaffold first:** `uv init engine` (Python 3.12, FastAPI) + `enum/` module + SQLite schema = Story 1.
- **Streaming `FileSource` interface:** `iter_files()` (metadata only) + `open(ref)→stream` (lazy chunks: local mmap / Graph streamed download). Engine never reads a source directly.
- **Modality router:** text→Presidio; image→YOLO26 + OCR + signature; non-image files NEVER touch YOLO.
- **`file_id` = `sha256(source_type : scope_id : native_id)`** — deterministic, unique-by-construction, stable. NOT random UUID.
- **Scan catalog (SQLite→Postgres)** = the spine: one row/file (file_id, content_hash, size, mtime, last_scanned_ts, ruleset_version, model_version, scan_status).
- **Delta = new/changed only by default**; ruleset-version sweep is an explicit opt-in trigger (`--reapply-ruleset`). Change feed = mtime+size→hash (local) / Graph `/delta` (OneDrive).
- **Dual scores:** risk_score (from enum weight) + confidence_score (drives escalation).
- **Risk-tiered escalation τ:** Critical 0.95 · High 0.90 · Medium 0.85 · Low 0.75; per-run Tier-2 budget governor.
- **Enum is single source of truth (`pii-detection-scope.md`):** engine emits ONLY codes present in the enum; `enum/generate.py` → engine constants + SQL seed.
- **Reproducibility mechanism:** versioned Tier-1 rules + pinned Tier-2 (temp 0, weights/prompt hash); every finding records detector_ver/model_ver/prompt_hash/timestamp.
- **GDPR invariants (hard gates):** never persist/log raw PII; mask at detection time; findings store enum+location+masked+scores only.
- **Streaming/perf:** sliding-window overlap for boundary-spanning entities; incremental hashing; spaCy `nlp.pipe` batching; image decode-once + resize + batch + ONNX/OpenVINO; gated OCR; process pool.
- **Eval harness:** labeled set (~200 text entities + ~50 images, span/bbox ground truth) + entity-level severity-stratified recall + calibration curve + determinism test (run 10×, diff).

### UX Design Requirements

N/A — no UX Design document. Scan engine is headless; owner/admin UI is a separate (deferred) domain.

### FR Coverage Map

- **Epic 1 (Detection Foundation & Text PII):** FR1, FR5, FR6, FR11, FR11a, FR11b, FR12, FR12a, FR13, FR17, FR18, FR19, FR20, FR21, FR23 · NFR4, NFR8(partial)
- **Epic 2 (Accuracy & Reproducibility Harness):** NFR6, NFR7, NFR8, NFR9 (validates all detection)
- **Epic 3 (Multi-Modal Detection / Images):** FR5a, FR7, FR8, FR9, FR10 · NFR4
- **Epic 4 (AI Escalation Safety-Net):** FR14 · NFR3, NFR5, NFR9(image)
- **Epic 5 (Scan Orchestration & Delta):** FR24, FR25, FR26 · NFR1
- **Epic 6 (OneDrive Source Integration):** FR2 · NFR1
- **Deferred (Growth/Vision, out of MVP):** FR3, FR4 (SharePoint/shares), FR5b & FR15 (video), FR16 (Art.9), FR22 (ownership fallback chain), FR27 (schedule)
- **Out of scan scope:** NFR2 (UI-facing)

## Epic List

### Epic 1: Detection Foundation & Text PII
Point the engine at a local folder and get text PII findings in the catalog, end-to-end. Provides the
scaffold, enum source-of-truth, scan catalog, deterministic file_id, streaming FileSource (local), text
extraction, Tier-1 text detectors, dual scores, no-raw-PII finding record, masked snippet, owner
attribution, and a basic full-scan runner — the backbone every other epic builds on.
**FRs covered:** FR1, FR5, FR6, FR11, FR11a, FR11b, FR12, FR12a, FR13, FR17, FR18, FR19, FR20, FR21, FR23

### Epic 2: Accuracy & Reproducibility Harness
Exists early so every detector is measured from day one. Labeled eval set (~200 text + ~50 images,
span/bbox ground truth, κ≥0.8 provenance), entity-level severity-stratified recall, FP rate, calibration
curve, and a determinism test (run 10×, diff). The eval-set-creation story has no detector dependency and
starts in parallel immediately (the long pole).
**NFRs covered:** NFR6, NFR7, NFR8, NFR9

### Epic 3: Multi-Modal Detection (Images)
Images now produce findings too. Modality router (non-image files never touch YOLO), image reading,
YOLO26 (face/plate/person), OCR (text-in-image → fed back to text detectors), signature detection, and
image performance (decode-once / resize / batch / ONNX-OpenVINO). Measured against the Epic 2 harness.
**FRs covered:** FR5a, FR7, FR8, FR9, FR10

### Epic 4: AI Escalation Safety-Net (Tier-2)
Low-confidence findings get a second opinion without blowing the budget. Risk-tiered escalation thresholds
(Critical 0.95 → Low 0.75), Tier-2 LLM/VLM verdict, per-run budget governor, and Tier-2 isolation so it
never gates the Tier-1 path.
**FRs covered:** FR14

### Epic 5: Scan Orchestration & Delta
Re-scans process only new/changed files; smarter rules trigger re-evaluation. Delta (new/changed-only
default via the catalog), ruleset-version sweep (opt-in `--reapply-ruleset`), and scan progress tracking
& completion reporting.
**FRs covered:** FR24, FR25, FR26

### Epic 6: OneDrive Source Integration
A second real source via Microsoft Graph, with an incremental change feed. OneDrive via Graph + `/delta`
token, behind the same FileSource seam — proving source-pluggability.
**FRs covered:** FR2

---

> **Self-contained story convention:** every story carries a `🔧 Implementer Context` block (target files,
> depends-on, contracts/refs, phase) so an independent subagent can implement it without the broader
> conversation. **Global hard gates (apply to ALL stories):** (1) never persist/log a raw PII value — mask
> at detection time; (2) the engine emits ONLY `machine_code`s present in `enum/classification_enum.yaml`;
> (3) `file_id` = `sha256(source_type:scope_id:native_id)`, never random; (4) snake_case end-to-end.

## Epic 1: Detection Foundation & Text PII

Point the engine at a local folder and get text PII findings in the catalog, end-to-end.

### Story 1.1: Project scaffold & monorepo skeleton

As a developer,
I want the monorepo scaffolded with the engine, web stub, enum, eval, and data directories,
So that every later story has a consistent place to add code and the engine boots.

**🔧 Implementer Context**
- **Files:** repo root — `engine/` (`uv init`, FastAPI app `engine/app/main.py`), `web/` (`npm create vite@latest -- --template react-ts`, stub OK), `enum/`, `eval/`, `data/`, `Makefile`, `.github/workflows/ci.yml`.
- **Depends on:** nothing (first story).
- **Contracts/refs:** layout + versions in architecture.md → Starter Template Evaluation (Python 3.12, FastAPI 0.136, Vite 8). CI = ruff + mypy + eslint + tsc.
- **Phase:** MVP.

**Acceptance Criteria:**
**Given** a clean checkout **When** I run `uv sync` in `engine/` and start `uvicorn app.main:app` **Then** the API boots and `GET /health` returns 200.
**And** `make test` runs an (empty) pytest suite green.
**And** CI runs ruff + mypy (engine) and eslint + tsc (web) on push.

### Story 1.2: Classification enum as single source of truth

As a developer,
I want the PII classification enum defined once and generated into engine constants + a SQL seed,
So that detectors, storage, and reporting all agree and no detector can emit an unlisted code.

**🔧 Implementer Context**
- **Files:** `enum/classification_enum.yaml` (rows: machine_code, display_label, modality, mvp, risk_weight, gdpr_focus), `enum/generate.py` (emits `engine/app/enums.py` constants + `data/enum_seed.sql`).
- **Depends on:** 1.1.
- **Contracts/refs:** seed rows verbatim from `pii-detection-scope.md` → "Classification Enum — COMPLETE mapping". risk_weight ∈ {Critical,High,Medium,Low}.
- **Phase:** MVP.

**Acceptance Criteria:**
**Given** `classification_enum.yaml` **When** I run `enum/generate.py` **Then** `engine/app/enums.py` and `data/enum_seed.sql` are produced with every row.
**And** a CI check fails if any detector references a code not present in the YAML.
**Given** the enum **When** code looks up a code **Then** it resolves to a `display_label` and `risk_weight`; raw `machine_code` is never the UI-facing value.

### Story 1.3: SQLite scan catalog, findings & audit schema + repositories

As a developer,
I want the catalog, finding, and audit_log tables plus a repositories layer and the file_id helper,
So that scans have a durable, privacy-by-design store with deterministic file identity.

**🔧 Implementer Context**
- **Files:** `engine/app/models/` (schema + Pydantic), `engine/app/repositories/`, `engine/app/identity.py` (`file_id = sha256(source_type:scope_id:native_id)`), `data/catalog.sqlite` (gitignored).
- **Depends on:** 1.2 (enum seed).
- **Contracts/refs:** table shapes in architecture.md → Data Architecture (`scan_catalog`, `finding`, `audit_log`); `file_id` recipe + scope table in → File Identity. `finding` has NO raw-PII column.
- **Phase:** MVP.

**Acceptance Criteria:**
**Given** a fresh DB **When** migrations/seed run **Then** `scan_catalog`, `finding`, `audit_log` exist and `classification_enum` is seeded.
**Given** the same `(source_type, scope_id, native_id)` **When** `file_id()` is called twice **Then** it returns the identical key (deterministic).
**Then** the `finding` table has no column capable of holding a raw PII value (enforced by schema review/test).
**And** repositories expose upsert-catalog / insert-finding / append-audit; only this layer touches SQL.

### Story 1.4: Streaming FileSource interface + LocalFolderSource

As a developer,
I want a streaming FileSource abstraction with a local-folder implementation,
So that the engine can enumerate and lazily read files without coupling to a source.

**🔧 Implementer Context**
- **Files:** `engine/app/sources/base.py` (`FileSource.iter_files()→Iterator[ref]` metadata-only; `open(ref)→stream` lazy chunks via `mmap`), `engine/app/sources/local_folder.py`.
- **Depends on:** 1.3 (file_id).
- **Contracts/refs:** architecture.md → Streaming & Performance (interface refinement); local `native_id` = normalized path, `scope_id` = source root.
- **Phase:** MVP.

**Acceptance Criteria:**
**Given** a folder **When** `iter_files()` is called **Then** it yields refs with path/size/mtime and reads no file contents.
**Given** a ref **When** `open(ref)` is consumed **Then** bytes arrive in chunks (memory bounded, not full-file load).
**And** each ref produces a stable `file_id` across repeated runs.

### Story 1.5: Text extraction with segment streaming & incremental hashing

As a developer,
I want a TextExtractor that yields offset-tagged text segments and hashes content incrementally,
So that large files are scanned within bounded memory and findings get accurate locations.

**🔧 Implementer Context**
- **Files:** `engine/app/detectors/text/extract.py` (`segments(stream)→Iterator[(text, base_offset)]`; txt/csv line, PDF page-by-page, docx paragraph), hashing util.
- **Depends on:** 1.4.
- **Contracts/refs:** architecture.md → Streaming & Performance (sliding-window overlap ≈256 chars; incremental sha256; PDF page = location). FR5.
- **Phase:** MVP.

**Acceptance Criteria:**
**Given** a multi-MB text file **When** extracted **Then** segments stream with correct global offsets and peak memory ≈ chunk size, not file size.
**Given** an entity spanning a chunk boundary **When** detected **Then** the overlap window catches it and it is not double-counted.
**Given** a PDF **When** extracted **Then** each segment carries its page number as location; `content_hash` equals a single-shot sha256 of the file.

### Story 1.6: Tier-1 deterministic text detectors (regex + checksum)

As a compliance engine,
I want deterministic regex/checksum detectors for structured P1/P2 identifiers,
So that high-precision PII is found cheaply and reproducibly.

**🔧 Implementer Context**
- **Files:** `engine/app/detectors/text/regex_checksum.py` implementing the `Detector` protocol; each emits enum code + span location + confidence + masked snippet.
- **Depends on:** 1.5, 1.2.
- **Contracts/refs:** codes EMAIL, PHONE_NUMBER, FAX_NUMBER, IBAN, CREDIT_CARD_NUMBER (Luhn), PASSPORT_NUMBER, DE_PERSONALAUSWEIS, DE_SOZIALVERSICHERUNGSNR, DE_STEUER_ID, DRIVERS_LICENSE_NUMBER, IP_ADDRESS, USERNAME (DE formats, checksum-validated). Presidio recognizers + custom DE. FR6, FR11, FR11a, FR11b, FR12, FR12a.
- **Phase:** MVP.

**Acceptance Criteria:**
**Given** text with an IBAN/PAN/German Tax-ID **When** scanned **Then** each is detected with the correct enum code, span offsets, and a masked snippet (e.g. `•••••4521`).
**Given** a checksum-invalid candidate **When** scanned **Then** it is rejected (confidence reflects checksum pass/fail).
**Then** running the same input twice yields byte-identical detector output (deterministic).
**And** no detector emits a code absent from the enum.

### Story 1.7: Tier-1 NER text detectors (names, addresses, travel history)

As a compliance engine,
I want NER-based detectors for semantic P1 attributes,
So that names, addresses, and travel history are caught beyond pattern matching.

**🔧 Implementer Context**
- **Files:** `engine/app/detectors/text/ner.py` (spaCy `de_core_news_lg` via Presidio; `nlp.pipe` batched over segments).
- **Depends on:** 1.5, 1.2.
- **Contracts/refs:** codes PERSON_NAME, HOME_ADDRESS, BILLING_SHIPPING_ADDRESS, TRAVEL_HISTORY (best-effort). German-first. FR6.
- **Phase:** MVP.

**Acceptance Criteria:**
**Given** German text with a person name + home address **When** scanned **Then** both are detected with correct enum codes and spans.
**Given** a batch of segments **When** scanned **Then** NER runs via `nlp.pipe` (batched), not one Doc per whole file.
**And** pinned spaCy model version is recorded for reproducibility.

### Story 1.8: Dual scoring & privacy-by-design finding write

As a compliance engine,
I want each detection scored for risk and confidence and written as a no-raw-PII finding with an audit row,
So that findings are rankable, escalatable, and regulator-defensible.

**🔧 Implementer Context**
- **Files:** `engine/app/services/scoring.py` (risk_score from enum risk_weight; confidence from detector), finding-write via repositories + `engine/app/audit.py`.
- **Depends on:** 1.6/1.7 (detections), 1.3 (store).
- **Contracts/refs:** architecture.md → Detection Engine & Scoring (dual independent scores); finding = location + enum + masked + scores; audit row = detector_ver + model_ver(null for T1) + prompt_hash(null) + timestamp. FR17, FR18, FR19, FR20.
- **Phase:** MVP.

**Acceptance Criteria:**
**Given** a detection **When** scored **Then** it gets a risk_score (from enum weight) and an independent confidence_score.
**When** written **Then** the finding row stores location + enum + masked snippet + both scores and **no raw PII**, and an audit_log row is appended with versions + timestamp.
**Then** a Critical-weight attribute (passport) ranks above a Low-weight one (IP) by risk_score.

### Story 1.9: Owner attribution (MVP)

As a compliance engine,
I want each finding attributed to a responsible data owner,
So that findings can later be routed to the person who can decide.

**🔧 Implementer Context**
- **Files:** `engine/app/services/ownership.py` (MVP: owner from local path mapping / mock identity table `owner_edge`/`file_ownership`).
- **Depends on:** 1.8.
- **Contracts/refs:** architecture.md → Ownership Resolution (MVP = mocked identity; fallback chain is Growth/FR22). FR21.
- **Phase:** MVP.

**Acceptance Criteria:**
**Given** a scanned file **When** a finding is written **Then** it carries an owner_user_id resolved from the mock identity mapping with `resolution_method` recorded.
**Given** an unresolvable owner **When** attributing **Then** it is logged and surfaced (never silently dropped).

### Story 1.10: Basic full-scan runner (end-to-end vertical slice)

As an administrator,
I want to trigger a full scan of a local folder,
So that the whole pipeline runs and the catalog fills with findings.

**🔧 Implementer Context**
- **Files:** `engine/app/services/scan_orchestrator.py` (FULL mode), `engine/app/api/scans.py` (`POST /scans`), `Makefile` target `make scan PATH=...`.
- **Depends on:** 1.4–1.9.
- **Contracts/refs:** architecture.md → Scan flow (steps 1–11). FR23, FR1, FR5.
- **Phase:** MVP.

**Acceptance Criteria:**
**Given** a folder of mixed text files **When** I run a full scan **Then** each file is read → detected → scored → written, and the catalog has one row per file plus findings.
**Then** re-running a full scan on unchanged files produces identical findings (deterministic).
**And** the run records ruleset_version + per-file scan_status=complete.

## Epic 2: Accuracy & Reproducibility Harness

Exists early so every detector is measured from day one. (Story 2.1 starts in parallel — no detector dependency.)

### Story 2.1: Build the labeled evaluation set

As a test architect,
I want a labeled, ground-truth eval set with provenance,
So that recall/precision claims are measurable, not asserted.

**🔧 Implementer Context**
- **Files:** `eval/labeled_set/` (text ~200 entities w/ span offsets; images ~50 w/ bbox), `eval/labeled_set/manifest.yaml` (label provenance, inter-annotator κ).
- **Depends on:** none (start immediately; uses a-klumpp synthetic samples as a starting point, not the test suite).
- **Contracts/refs:** PRD Success Criteria (eval-set prerequisite, κ≥0.8); enum codes for labels.
- **Phase:** MVP.

**Acceptance Criteria:**
**Given** the labeled set **When** loaded **Then** each label has an enum code + char span (text) or bbox (image) + source provenance.
**Then** the manifest reports inter-annotator agreement (Cohen's κ ≥ 0.8) and category/modality distribution.

### Story 2.2: Entity-level recall & false-positive harness

As a test architect,
I want to score the engine against the labeled set at entity level, stratified and severity-weighted,
So that easy wins can't mask catastrophic misses.

**🔧 Implementer Context**
- **Files:** `eval/run_eval.py` (run engine over labeled set, match spans/bboxes, compute recall + FP, stratify by category + modality, weight by severity).
- **Depends on:** 2.1, and at least Epic 1 detectors for a real number.
- **Contracts/refs:** NFR6 (≥90% text / ≥80% image P1), NFR7 (FP ≤25%), NFR9 (top-severity gated separately).
- **Phase:** MVP.

**Acceptance Criteria:**
**Given** the engine + labeled set **When** `run_eval.py` runs **Then** it reports entity-level recall and FP rate, broken down by PII category and modality.
**Then** top-severity (Critical/Art.9) recall is reported and gated separately from aggregate recall.

### Story 2.3: Confidence calibration curve

As a test architect,
I want a calibration curve of confidence vs actual precision,
So that the escalation thresholds (τ) can be tuned with data, not guesses.

**🔧 Implementer Context**
- **Files:** `eval/calibration.py` (bin findings by confidence, compute actual precision per bin, emit curve).
- **Depends on:** 2.2.
- **Contracts/refs:** feeds Epic 4 τ tuning; PRD Technical Success (calibration curve or name the gap).
- **Phase:** MVP.

**Acceptance Criteria:**
**Given** scored findings vs ground truth **When** calibration runs **Then** it outputs precision per confidence bin.
**And** if calibration is insufficient, the gap is reported explicitly rather than hidden.

### Story 2.4: Determinism test

As a test architect,
I want a test that runs the Tier-1 corpus 10× and diffs the output,
So that reproducibility (a legal property) is proven, not claimed.

**🔧 Implementer Context**
- **Files:** `eval/test_determinism.py`.
- **Depends on:** Epic 1 detectors.
- **Contracts/refs:** NFR8 (100% identical); architecture.md → Reproducibility Mechanism.
- **Phase:** MVP.

**Acceptance Criteria:**
**Given** a fixed corpus **When** Tier-1 runs 10× **Then** all 10 outputs are byte-identical.
**And** the test fails loudly on any nondeterminism, reporting the diff.

## Epic 3: Multi-Modal Detection (Images)

### Story 3.1: Modality router

As a compliance engine,
I want files routed by modality so non-image files never hit the vision pipeline,
So that throughput and cost stay low and detections stay correct.

**🔧 Implementer Context**
- **Files:** `engine/app/detectors/router.py` (classify by MIME + extension + magic bytes; text→text path; image→image path; PDF native-text→text, scanned/image-only→OCR).
- **Depends on:** 1.5 (text path exists).
- **Contracts/refs:** architecture.md → Modality routing. Office-embedded images = Growth (treat Office as text-only in MVP).
- **Phase:** MVP.

**Acceptance Criteria:**
**Given** a `.txt`/`.docx` **When** routed **Then** YOLO/image-OCR are never invoked.
**Given** an image file **When** routed **Then** it enters the image pipeline.
**Given** a scanned (image-only) PDF **When** routed **Then** it goes to the OCR path; a native-text PDF goes to the text path.

### Story 3.2: Image pipeline scaffold (decode-once, resize, batch)

As a compliance engine,
I want an efficient image pipeline that decodes once and batches,
So that image scanning meets the CPU budget.

**🔧 Implementer Context**
- **Files:** `engine/app/detectors/image/pipeline.py` (decode→shared array; resize/letterbox to model input; batch image-modality files).
- **Depends on:** 3.1.
- **Contracts/refs:** architecture.md → Streaming & Performance (images); NFR4.
- **Phase:** MVP.

**Acceptance Criteria:**
**Given** several images **When** scanned **Then** each is decoded once and shared across detectors; inference runs in batches.
**And** images are resized/letterboxed to the model input before inference.

### Story 3.3: YOLO26 face/person & licence-plate detection

As a compliance engine,
I want YOLO detection of faces/persons and licence plates in images,
So that biometric and vehicle PII is flagged deterministically.

**🔧 Implementer Context**
- **Files:** `engine/app/detectors/image/yolo.py` (Ultralytics YOLO26, pinned weights, NMS-free; ONNX/OpenVINO export for CPU).
- **Depends on:** 3.2, 1.8 (scoring/write), 1.2 (codes FACE, LICENSE_PLATE).
- **Contracts/refs:** FR8, FR9; codes FACE (risk High, Art.9 biometric), LICENSE_PLATE. Determinism via pinned weights.
- **Phase:** MVP.

**Acceptance Criteria:**
**Given** an image with a face **When** scanned **Then** a FACE finding is written with a bbox location + confidence.
**Given** an image with a licence plate **When** scanned **Then** a LICENSE_PLATE finding is written.
**Then** repeated runs on the same image are identical (pinned weights, deterministic post-processing).

### Story 3.4: OCR text-in-image → text detectors

As a compliance engine,
I want OCR on images feeding extracted text back through the Tier-1 text detectors,
So that PII printed inside scans/photos is caught.

**🔧 Implementer Context**
- **Files:** `engine/app/detectors/image/ocr.py` (EasyOCR/Tesseract; recognize on detected text regions; downscale; skip tiny images).
- **Depends on:** 3.2, 1.6 (text detectors reused on OCR output).
- **Contracts/refs:** FR7; OCR text → text Tier-1 → enum findings with image location.
- **Phase:** MVP.

**Acceptance Criteria:**
**Given** an image of a passport scan **When** OCR runs **Then** the extracted text is fed through text detectors and a PASSPORT_NUMBER finding is written with image location.
**And** OCR is skipped for icon/tiny images by size threshold.

### Story 3.5: Signature detection

As a compliance engine,
I want signature detection in images,
So that handwritten signatures are flagged as personal data.

**🔧 Implementer Context**
- **Files:** `engine/app/detectors/image/signature.py` (small custom model/heuristic; lowest priority on de-scope ladder).
- **Depends on:** 3.2, 1.2 (code SIGNATURE).
- **Contracts/refs:** FR10; code SIGNATURE (risk High). PRD risk-ladder: signature is first to drop if behind.
- **Phase:** MVP.

**Acceptance Criteria:**
**Given** an image containing a signature **When** scanned **Then** a SIGNATURE finding is written with a bbox + confidence.
**And** the detector is independently toggleable (de-scope ladder) without breaking the image pipeline.

## Epic 4: AI Escalation Safety-Net (Tier-2)

### Story 4.1: Risk-tiered escalation policy + budget governor

As a compliance engine,
I want low-confidence findings escalated by a risk-weighted threshold within a budget,
So that recall is protected on high-risk PII without runaway cost.

**🔧 Implementer Context**
- **Files:** `engine/app/services/escalation_policy.py` (escalate if `confidence < τ(risk_weight)`; τ: Critical 0.95/High 0.90/Medium 0.85/Low 0.75; per-run Tier-2 budget cap; adaptive raise/queue on overflow).
- **Depends on:** 1.8 (scored findings), 2.3 (calibration informs τ).
- **Contracts/refs:** architecture.md → Escalation Threshold; NFR3 (<10%).
- **Phase:** MVP.

**Acceptance Criteria:**
**Given** a Critical finding at confidence 0.92 **When** the policy runs **Then** it is escalated (0.92<0.95); a Low finding at 0.80 is not.
**Given** escalation volume exceeds the per-run budget **When** scanning **Then** τ is raised adaptively / overflow queued, keeping Tier-2 under the cap.

### Story 4.2: Tier-2 text LLM second-opinion verdict

As a compliance engine,
I want a Tier-2 LLM verdict on escalated text findings,
So that ambiguous text PII gets a recall safety-net — reproducibly and in-perimeter.

**🔧 Implementer Context**
- **Files:** `engine/app/detectors/tier2/llm_text.py` (temp 0; pinned model+version; hashed prompt; ephemeral PII in-memory only; record model_ver+prompt_hash in audit).
- **Depends on:** 4.1.
- **Contracts/refs:** demo = hosted LLM on synthetic data (PRD-permitted); prod = self-hosted in-perimeter (NFR12). Reproducibility mechanism.
- **Phase:** MVP.

**Acceptance Criteria:**
**Given** an escalated text finding **When** Tier-2 runs **Then** it returns confirm/deny + adjusted confidence, and the audit row records model_ver + prompt_hash + timestamp.
**Then** the PII snippet sent to Tier-2 is held in memory only and discarded after the verdict (never persisted/logged).

### Story 4.3: Tier-2 image VLM second-opinion verdict

As a compliance engine,
I want a Tier-2 VLM verdict on escalated image findings,
So that ambiguous faces/plates/signatures get a second look.

**🔧 Implementer Context**
- **Files:** `engine/app/detectors/tier2/vlm_image.py` (same reproducibility + ephemeral rules as 4.2).
- **Depends on:** 4.1, Epic 3.
- **Contracts/refs:** FR14 (image side); NFR9 (top-severity image recall).
- **Phase:** MVP.

**Acceptance Criteria:**
**Given** a low-confidence FACE/SIGNATURE finding **When** Tier-2 VLM runs **Then** it returns a verdict + adjusted confidence with audit provenance.

### Story 4.4: Tier-2 isolation (never gates Tier-1)

As a compliance engine,
I want Tier-2 inference isolated from the Tier-1 path,
So that the common cheap path is never blocked by heavy inference.

**🔧 Implementer Context**
- **Files:** `engine/app/services/scan_orchestrator.py` (Tier-2 dispatched async/separate worker; Tier-1 results land in catalog immediately; Tier-2 updates findings later).
- **Depends on:** 4.1.
- **Contracts/refs:** NFR5.
- **Phase:** MVP.

**Acceptance Criteria:**
**Given** a scan with some escalations **When** running **Then** Tier-1 findings are written without waiting on Tier-2; Tier-2 verdicts update findings asynchronously.
**And** a slow/failed Tier-2 call never blocks or aborts the Tier-1 scan.

## Epic 5: Scan Orchestration & Delta

### Story 5.1: Delta scan — process only new/changed files

As an administrator,
I want re-scans to process only new and changed files,
So that continuous scanning is cheap (cost ∝ change volume).

**🔧 Implementer Context**
- **Files:** `engine/app/services/scan_orchestrator.py` (DELTA mode: enumerate metadata; lookup catalog; PROCESS if new or size/mtime differ→hash-confirm; SKIP if unchanged; remove/flag rows for deletes/moves).
- **Depends on:** 1.10 (full-scan runner), 1.3 (catalog).
- **Contracts/refs:** architecture.md → Delta behavior; FR24; NFR1 (delta materially faster than full).
- **Phase:** MVP.

**Acceptance Criteria:**
**Given** a completed full scan **When** I edit one file and run delta **Then** only that file is read+detected; unchanged files cost a stat() only (not re-read).
**Given** a deleted file **When** delta runs **Then** its catalog row is removed (accounted-for guarantee preserved).
**Then** a delta scan with no changes processes zero files.

### Story 5.2: Ruleset-version sweep (opt-in re-evaluation)

As an administrator,
I want an opt-in sweep that re-evaluates files when detectors improve,
So that previously-clean files are re-checked when rules get smarter — without a full re-scan by default.

**🔧 Implementer Context**
- **Files:** scan_orchestrator `--reapply-ruleset` flag (select `WHERE ruleset_version < current`, re-process those).
- **Depends on:** 5.1.
- **Contracts/refs:** architecture.md → "Re-scan set = union of change-feed and ruleset query"; the sweep is explicit/opt-in. FR25.
- **Phase:** MVP.

**Acceptance Criteria:**
**Given** a bumped ruleset_version **When** I run delta WITHOUT the flag **Then** unchanged files are NOT reprocessed.
**Given** the same **When** I run with `--reapply-ruleset` **Then** files with stored ruleset_version < current are re-evaluated and their version updated.

### Story 5.3: Scan progress tracking & completion

As an administrator,
I want to see scan progress and completion,
So that I know coverage and when a scan is done.

**🔧 Implementer Context**
- **Files:** scan_orchestrator progress counters; `engine/app/api/scans.py` (`GET /scans/{id}` → files_total/scanned/findings/status).
- **Depends on:** 1.10.
- **Contracts/refs:** FR26; scan_status lifecycle `queued→scanning→complete|failed`.
- **Phase:** MVP.

**Acceptance Criteria:**
**Given** a running scan **When** I query its status **Then** I get files scanned vs total, findings count, and state.
**When** it finishes **Then** status=complete and totals are final.

## Epic 6: OneDrive Source Integration

### Story 6.1: OneDrive FileSource via Microsoft Graph

As an administrator,
I want to scan a user's OneDrive through Microsoft Graph,
So that the engine works on a real M365 source, not just local files.

**🔧 Implementer Context**
- **Files:** `engine/app/sources/onedrive_graph.py` (OAuth/device-code auth; `iter_files()` via Graph driveItem listing; `open(ref)` via streamed download).
- **Depends on:** 1.4 (FileSource interface).
- **Contracts/refs:** `native_id` = Graph `driveItem.id`, `scope_id` = `drive_id`. FR2. Graph OAuth flagged as the long pole — spike early; local remains fallback.
- **Phase:** MVP.

**Acceptance Criteria:**
**Given** valid Graph auth **When** `iter_files()` runs on a OneDrive **Then** it yields file refs with stable `file_id` (drive_id:item_id) without downloading content.
**Given** a ref **When** `open(ref)` runs **Then** content streams from Graph in chunks; the same pipeline (Epics 1/3/4) produces findings unchanged.

### Story 6.2: Graph /delta incremental change feed

As an administrator,
I want OneDrive delta scans driven by the Graph /delta token,
So that re-scans at scale avoid full re-enumeration.

**🔧 Implementer Context**
- **Files:** `onedrive_graph.py` `changes_since(token)` (Graph `/delta`; persist deltaLink token per source).
- **Depends on:** 6.1, 5.1 (delta orchestration).
- **Contracts/refs:** architecture.md → Delta change-signal (Graph /delta = the scale answer); NFR1.
- **Phase:** MVP.

**Acceptance Criteria:**
**Given** a prior OneDrive scan with a stored delta token **When** a delta scan runs **Then** only created/modified/deleted items are returned (no full enumeration) and processed per the delta rules.
**And** deletions from the change feed remove the corresponding catalog rows.
