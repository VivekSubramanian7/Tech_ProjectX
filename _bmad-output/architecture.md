---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8]
lastStep: 8
status: 'complete'
completedAt: '2026-05-30'
inputDocuments:
  - '_bmad-output/prd.md'
  - '_bmad-output/pii-detection-scope.md'
  - '_bmad-output/prior-art-landscape.md'
  - '_bmad-output/architecture-open-questions.md'
workflowType: 'architecture'
project_name: 'Automated GDPR Compliance (Bosch Data Discovery)'
user_name: 'Vivek'
date: '2026-05-30'
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Project Context Analysis

### Requirements Overview

**Functional Requirements:** 56 FRs across 8 areas. Architecturally they cluster into three
decoupled subsystems communicating only via a shared findings catalog:
- Source ingestion (FR1–FR5b): pluggable file-source interface; local + OneDrive [MVP], SharePoint
  + file shares [Growth]; per-modality readers (text/image [MVP], video [Growth]).
- Detection & classification (FR6–FR16): cascading Tier-1 deterministic → Tier-2 AI escalation;
  controlled-vocabulary enum output.
- Scoring & findings (FR17–FR22): dual independent scores (risk = legal severity; confidence =
  detection certainty); privacy-by-design record (location + enum + scores, no raw PII).
- Scan orchestration (FR23–FR27): full + delta scans; ruleset-version invalidation; progress.
- Owner remediation / escalation / admin (FR28–FR45): 3 RBAC-gated web surfaces.
- Audit, compliance & access (FR46–FR51): immutable audit log; reproducibility; retention; RBAC;
  DPO-cannot-see-PII guarantee.

**Non-Functional Requirements:** 22 NFRs. Architecture-shaping: data sovereignty / in-perimeter
inference (NFR12), reproducibility as a legal property (NFR8), privacy-by-design findings model
(NFR11), Tier-2 ≤10% escalation (NFR3), CPU-only Tier-1 budget (NFR4), horizontal scale (NFR15),
delta-proportional steady-state cost (NFR16), immutable/tamper-evident audit (NFR14), RBAC least-
privilege (NFR13).

**Scale & Complexity:**
- Primary domain: hybrid data-pipeline + ML system + B2B SaaS web app
- Complexity level: High / Enterprise (300k drives, hard regulatory floor, multi-modal AI)
- Estimated architectural components: ~7 (source connectors, scan orchestrator, Tier-1 detectors,
  Tier-2 inference service, findings catalog/store, web API + 3 UIs, audit/identity layer)

### Technical Constraints & Dependencies

- **Data sovereignty (hard):** no PII to third-party AI; Tier-2 self-hosted / in Bosch tenant.
  ("Cloud" inside Bosch's own Azure/M365 tenant is sovereignty-safe — egress to external AI is not.)
- **Reproducibility (legal):** version-locked Tier-1 rules + pinned Tier-2 model/version; every
  finding records detector ver, model ver, prompt hash, timestamp.
- **Enum as single source of truth:** engine must not emit a classification absent from
  pii-detection-scope.md; new detector ⇒ new enum row first.
- **Privacy-by-design store:** findings hold enum + location + scores, never raw PII; Tier-2 PII
  cache is ephemeral. The catalog must not become a honeypot.
- **Identity/org-graph dependency:** Entra/AD SSO + manager graph for auth, RBAC, and escalation
  routing; stale org data is an operational risk.
- **External APIs:** Microsoft Graph (incl. /delta), SMB/NTFS + USN journal, Teams.

### Cross-Cutting Concerns Identified

- Reproducibility & immutable audit (spans engine, store, all actions)
- Data sovereignty / in-perimeter inference (spans Tier-2, deployment topology)
- RBAC & least-privilege incl. DPO-never-sees-PII (spans all surfaces + store)
- Classification-enum consistency (spans detectors, store, UI labels, reporting)
- Delta-catalog integrity incl. deletes/moves & ruleset-version invalidation
- Ownership resolution & escalation routing (owner → manager → delegate/DPO)

### Open Architectural Decisions (carried from architecture-open-questions.md)

1. Inference / deployment topology — **RESOLVED** (see Deployment & Topology Decision below)
2. Reproducibility mechanism — to formalize (version-lock + per-finding provenance)
3. Tier-1→Tier-2 escalation threshold — OPEN (most load-bearing parameter)
4. Delta-scan invalidation — resolved mechanism (scan catalog + Graph /delta / USN) — to ratify
5. Data-ownership resolution policy — to harden (fallback chain)
6. Video scope — deferred to Growth

## Deployment & Topology Decision (Open-Q #1 — RESOLVED)

**Production target: "compute goes to the data" in-tenant hybrid.**
- **Central plane in the Bosch Azure tenant** — scan orchestrator, findings catalog, Tier-2 GPU pool
  (self-hosted, scale-to-zero), web API + 3 RBAC surfaces. In-tenant ⇒ sovereignty-safe; M365 reads
  via Graph never leave the tenant (zero egress).
- **M365 sources (OneDrive/SharePoint):** Tier-1 workers run in-tenant, read via Graph in place.
- **On-prem file shares:** Tier-1 **edge workers** (same container image) scan in place and send
  **findings only** (enum + location + risk + confidence, never raw PII) to the central catalog.
- **On-prem Tier-2 path:** ephemeral low-confidence snippet shipped over the internal Bosch network
  to the central in-tenant GPU pool; verdict returned, content discarded (stays in-perimeter). No
  separate regional GPU fleet.
- **Rejected:** pure-central (on-prem WAN egress + PII movement) and pure-desktop (300k unmanaged
  agents, can't reach shared SharePoint).
- **Cost rationale (the build-vs-buy proof):** Tier-1 on commodity CPU on everything; Tier-2 GPU
  scales to ~zero and only sees the ambiguous <10%; delta+catalog makes steady-state cost ∝ change
  volume, not estate size (NFR16) — structurally cheaper than Purview/Varonis PAYG.

**Build decision (this hackathon): MVP single-app *emulation* of the topology via seams.**
The 48h build is one local process that faithfully models the hybrid through abstractions, NOT real
infrastructure. The Azure deployment is a **stretch goal if time allows**.

| Production component | MVP emulation | Proves in demo |
|---|---|---|
| File-source interface (in-tenant Graph vs on-prem edge) | One `FileSource` interface; `LocalFolderSource` + `OneDriveGraphSource` impls | Sources interchangeable behind one seam; both feed one catalog |
| Scan worker (container at edge/in-tenant) | Same `scan(file)→findings` worker called in-process | Worker already portable; prod swaps in-proc → queue |
| Findings-only wire contract (edge → central) | Enforced in-app: catalog gets enum+location+scores, never raw PII | Sovereignty + privacy-by-design made visible |
| Central findings catalog (Postgres) | SQLite, identical schema | Delta logic is schema-driven → same code in prod |
| Tier-2 GPU pool (self-hosted in-tenant) | Hosted LLM/VLM on synthetic a-klumpp data only (PRD-permitted for demo) | Endpoint moves in-perimeter for prod; architecture unchanged |
| Change feeds (Graph /delta, USN) | OneDrive = real Graph /delta; local = mtime+size→hash (stands in for USN) | Real production delta mechanism demoed on OneDrive path |

**Demo script:** point both sources at content → findings-only into one SQLite catalog → Owner queue
populated from both → edit a file + bump ruleset version → delta touches only changed/invalidated
files → open catalog live: no raw PII. The single app is a faithful scale model of the hybrid.

## Starter Template Evaluation

### Primary Technology Domain
Hybrid: Python ML/data-pipeline backend (scan engine + FastAPI) + React SPA frontend (3 RBAC views).
No single starter spans both → two scaffolds in one monorepo (`/engine`, `/web`, shared `/enum`).

### Starter Options Considered
- Backend: bare FastAPI scaffold via `uv` (modern fast Python pkg mgr) vs cookiecutter templates.
  Chosen: minimal `uv` + FastAPI — ML deps (Presidio/YOLO/OCR) are specific; heavy templates add noise.
- Frontend: create-vite React-TS vs Next.js. Chosen: create-vite (React+Vite SPA locked in step 2 fork).

### Selected Foundation (versions verified via web, May 2026)

**Backend / engine — Python + FastAPI** (FastAPI 0.136.x · Presidio 2.2.362 · Ultralytics YOLO26)
```bash
uv init engine && cd engine          # Python 3.12 (FastAPI supports 3.10–3.14)
uv add fastapi "uvicorn[standard]" presidio-analyzer presidio-anonymizer \
       spacy ultralytics easyocr pydantic
python -m spacy download de_core_news_lg   # German-first NER (locale = Germany)
```

**Frontend — React + Vite SPA** (Vite 8.x / create-vite 9.x; Node 20.19+/22.12+)
```bash
npm create vite@latest web -- --template react-ts
```

### Architectural Decisions Provided
- **Language & runtime:** Python 3.12 (engine+API); TypeScript + React (web); Node 22 LTS (build only).
- **Detection libs:** Presidio (text NER/regex/checksum) · YOLO26 (face/plate/person — NMS-free, CPU-fast,
  deterministic with pinned weights) · EasyOCR/Tesseract (OCR). German spaCy model (locale-first).
- **API:** FastAPI async REST + auto-generated OpenAPI → typed client for the 3 UIs.
- **Catalog:** SQLite (MVP) with schema portable to Postgres (prod).
- **Repo layout:** monorepo — `/engine` (scan workers + detectors + API), `/web` (SPA),
  `/enum` (classification enum = shared single source of truth), `/eval` (labeled eval set + harness).
- **Determinism note:** pin YOLO26 weights + deterministic inference flags; pin spaCy model version;
  YOLO26 NMS-free removes tie-break nondeterminism; record all versions per finding (feeds open-Q #2).

**Note:** Project init (both scaffolds + enum module + SQLite schema) = the first implementation story.

## Data & Infrastructure Decision

**Storage:** SQLite (MVP) → Postgres (prod), one schema. The catalog is the spine (scan state + findings
+ ownership edges + audit log). No separate stores added.

**Redis — NOT used.**
- Job queue: MVP dispatch is in-process; prod uses Azure Service Bus or a Postgres-backed queue (better
  tenant fit than running Redis).
- Cache: catalog is the state; no hot read-path to cache at this scale.
- Ephemeral Tier-2 PII: kept in-memory per job and discarded — putting PII in Redis would create the
  honeypot NFR11 forbids.
- Graph API rate-limit/backoff (NFR20): handled in-process.

**Graph database — NOT used.**
- "Microsoft Graph" is M365's REST **API** (a data source we call), NOT a graph DB.
- The org graph (employee → manager → department → DPO) is queried **shallow** (1–4 bounded hops), so it
  is modeled as a **relational edge table** (`user_id, manager_id, role, delegate_id`), resolved by
  iterative lookup / recursive CTE. Source of truth = Entra ID (nightly sync in prod; mocked in MVP).
- Org-unit coverage/trends (FR44, J4) = relational `GROUP BY`, not traversal.
- **Revisit-if:** Vision-stage estate-wide permission-reachability or deep data-lineage analytics → then
  re-evaluate a graph DB. Not before.

**Net MVP infra:** SQLite only. No Redis, no graph DB, no broker — consistent with the low-resource/cheap pitch.

## Core Architectural Decisions

### Decision Priority Analysis
**Critical (block implementation):** detection-engine pipeline & dual-score model; escalation threshold
(open-Q #3); catalog data model; delta-invalidation (open-Q #4); reproducibility mechanism (open-Q #2).
**Important (shape architecture):** ownership resolution (open-Q #5); RBAC enforcement & DPO-never-sees-PII;
auth (MVP mock → Entra).
**Deferred (post-MVP):** Service Bus queue; Postgres migration; distributed/edge workers; video; P3.

### Detection Engine & Scoring
- **Cascading pipeline:** modality router (text / image) → Tier-1 deterministic detectors on ALL files →
  risk-weighted escalation of the uncertain minority to Tier-2 (LLM text / VLM image).
- **Tier-1:** Presidio (text NER/regex/checksum) + YOLO26 (face/plate/person, NMS-free) + EasyOCR/Tesseract.
- **Dual independent scores per finding:** `risk_score` (legal severity, from enum risk weight — ranks the
  owner queue, never hidden) and `confidence_score` (detection certainty — drives escalation). Orthogonal.

### Escalation Threshold (open-Q #3 — RESOLVED: recall-first, risk-tiered)
- Escalate a Tier-1 finding to Tier-2 when `confidence < τ(risk_weight)`:
  Critical τ=0.95 · High τ=0.90 · Medium τ=0.85 · Low τ=0.75. (FN = highest cost → eager on high-risk.)
- **Budget governor:** per-run Tier-2 cap; if escalation volume exceeds the NFR3 <10% ceiling, raise τ
  adaptively / queue overflow.
- **Calibration-driven:** τ tuned against the labeled eval set via a confidence-bin → precision curve;
  escalation fraction verified < budget.
- **Feedback loop (no full re-scan):** log Tier-2 verdict vs triggering Tier-1 confidence; recompute
  calibration periodically; re-evaluate ONLY catalog findings near the boundary.

### Data Architecture (SQLite → Postgres, one schema)
- `classification_enum` (machine_code PK, display_label, modality, mvp_flag, risk_weight, gdpr_focus) —
  seeded from pii-detection-scope.md; **engine may emit only codes present here** (hard rule).
- `scan_catalog` (file_id PK, source_id, path, content_hash, size, mtime, last_scanned_ts,
  ruleset_version, model_version, scan_status) — the spine; one row per file.
- `finding` (id, file_id→catalog, classification_code→enum, location {page/offset/bbox}, masked_snippet,
  risk_score, confidence_score, tier, detector_version, model_version, prompt_hash, created_ts,
  resolution_status) — **NO raw PII value** (NFR11).
- `owner_edge` (user_id, manager_id, role, delegate_id) + `file_ownership` (file_id, owner_user_id,
  resolution_method) — relational org edges (no graph DB).
- `remediation_action` (finding_id, action {keep/delete/escalate}, reason_code, actor, soft_delete_until, ts).
- `audit_log` (id, entity_type, entity_id, action, actor, justification, detector_version, model_version,
  prompt_hash, timestamp) — **append-only / tamper-evident**, retained beyond scan cycles (Art. 5(2)).

### Delta-Scan Invalidation (open-Q #4 — RATIFIED)
- Re-scan a file iff: new / content-hash changed (mtime+size cheap pre-filter) / ruleset|model version
  newer than catalog's stored version (the "smarter rules force re-eval of previously-clean files" case) /
  previously low-confidence-escalated.
- Change signal per source: OneDrive/SharePoint = Graph `/delta` token (no full enumeration — the scale
  answer); NTFS shares = USN journal; local/generic = mtime+size → hash.
- Handle deletes/moves (update/remove catalog rows) to preserve the "accounted-for" guarantee.

### Reproducibility Mechanism (open-Q #2 — FORMALIZED)
- Tier-1 rules versioned as code → `ruleset_version` (semver; bump on any detector change).
- Tier-2 pinned: model name+version+weights hash, temperature 0, hashed prompt template.
- Every finding records detector_version + model_version + prompt_hash + timestamp (catalog + audit log).
- Proof: run corpus 10× and diff Tier-1 output → 100% identical (NFR8). Tier-2 documented non-deterministic
  but version-anchored.

### Ownership Resolution (open-Q #5 — HARDENED)
- Fallback chain: direct owner (OneDrive) → "Master of Data" / line manager → department DPO/delegate.
- Orphaned / departed-employee files → reassign to manager/delegate; `resolution_method` recorded.
- Source = Entra org graph (nightly sync, prod) / mocked identity table (MVP). Wrong/void routing = logged
  and surfaced, never silently dropped (preserves accountability).

### Authentication & Security
- **MVP:** mocked identity (seeded users + role switch) — FR49 permits; **Prod:** Entra ID SSO (OIDC).
- **RBAC enforced at the API layer** per the PRD RBAC matrix; role gates every endpoint.
- **DPO-never-sees-PII enforced structurally:** raw PII is never stored, AND the API never returns
  owner-scoped finding detail to the admin/DPO role (aggregates only) — defense in depth (NFR13, FR51).
- **Encryption:** TLS in transit; at-rest encryption on catalog/findings/audit store.

### API & Frontend
- **API:** FastAPI async REST + auto OpenAPI → typed client; consistent error envelope; retry/backoff on
  Graph (NFR20).
- **Scan dispatch:** in-process (MVP) → queue (prod). Engine and web app communicate ONLY via the catalog.
- **Frontend:** React+Vite SPA; 3 role-gated route trees (Owner / Line-Manager / DPO) sharing one component
  library; lightweight state (TanStack Query for server state, minimal client state).

### Decision Impact / Sequence
1. Enum module + SQLite schema → 2. Tier-1 text detectors + catalog write → 3. file-source interface
(local) → 4. one finding card + one owner action → 5. image Tier-1 (YOLO/OCR) → 6. Tier-2 escalation +
thresholds → 7. delta + ruleset-bump demo → 8. admin dashboard → 9. OneDrive Graph source.

## Scan Process Flow, Delta & File Identity

### Scan flow (end-to-end, per file)
`scan_orchestrator` drives all scans through the `FileSource` seam; the engine never reads a source directly.
```
1. source.iter_files()                  # FileSource yields refs (local walk / Graph list) — metadata only
2. per ref, cheap pre-check vs catalog  # size+mtime+ruleset_version → decide PROCESS or SKIP (see Delta)
3. source.open(ref) → stream             # lazy chunks (local mmap / Graph streamed download); PROCESSED files only
4. content_hash updated incrementally over chunks  # never holds the whole file in memory
5. MODALITY ROUTER (see below)           # text vs image vs video — branch point
6. Tier-1 detectors emit candidate findings (enum_code, location, raw confidence)
7. ESCALATION: confidence < τ(risk_weight) → Tier-2 (LLM text / VLM image)   # risk-tiered, minority only
8. SCORING: risk_score (from enum) + final confidence_score
9. OWNERSHIP: resolve via fallback chain
10. repositories.write(): upsert scan_catalog row + insert findings (enum+location+masked+scores, NO raw PII)
    + append audit_log rows (detector_ver, model_ver, prompt_hash, ts)
11. persist source cursor (delta token / USN position)   # enables next-run delta
```

### Delta behavior — DEFAULT = only new/changed files are PROCESSED
The catalog persists between runs, so first run = full scan (everything "new"); every later run processes
**only new and genuinely-changed files**. Key distinction: **enumerate (cheap metadata) ≠ process (read+detect)**.

Subsequent directory/source scan:
```
ENUMERATE entries (scandir / Graph /delta / USN)  — metadata only, no content read
  • not in catalog                     → NEW       → PROCESS
  • in catalog, size+mtime UNCHANGED    → SKIP      ← majority; cost = one stat()
  • in catalog, size/mtime DIFFERS      → hash; differs → CHANGED → PROCESS; same → SKIP (refresh mtime)
  • catalog row not seen in enumeration → DELETED/MOVED → remove/flag (preserve "accounted for")
```
Change signal per source: OneDrive/SharePoint = Graph `/delta` token (no full re-enumeration — the scale
win); NTFS = USN journal; local = mtime+size→hash. An unchanged file costs only a `stat()`; never re-read.
→ steady-state cost ∝ change volume, not estate size (NFR16).

**Re-scan set = union of (A) change feed [content changed] and (B) catalog query
`WHERE ruleset_version < current` [rules got smarter].** (B) is the ONE deliberate exception that
reprocesses *unchanged* files — and it is an **explicit, opt-in trigger** (`--reapply-ruleset`), NOT normal
per-run behavior. A routine scan with no rule change touches only new/changed files, full stop.

### Modality routing — non-image files NEVER touch YOLO
```
modality = classify(file)            # MIME + extension, confirmed with magic bytes
  ├─ TEXT/DOCUMENT → extract text → Tier-1 text detectors only        # NO YOLO, NO image OCR
  ├─ IMAGE         → YOLO26 (face/plate/person) + OCR + signature; OCR text → re-fed to text detectors
  └─ VIDEO [Growth]→ frame sampling → image pipeline per frame
```
- A `.txt/.docx/.eml` never enters the vision pipeline (cost/throughput — NFR1/NFR4; correctness).
- PDFs route per-file: native-text PDF → text path; scanned/image-only PDF → OCR path.
- Embedded images inside Office docs = **Growth** (MVP treats Office docs as text-only) — conscious scope line.
- Image files are batched for efficient YOLO inference (further throughput win on the minority image set).

### File Identity (`file_id`) — deterministic, unique-by-construction, stable
`file_id` must be (1) **unique** (distinct files never collide) AND (2) **stable** (same file → same id every
run, or delta breaks). A random UUID would break stability. Source-native IDs are unique only *within a
scope*, so the key must namespace down to that scope:

```
file_id = sha256( source_type : scope_id : native_id )
```
| Source | native_id | unique within | scope_id must include |
|---|---|---|---|
| OneDrive/SharePoint | Graph `driveItem.id` (stable across rename/move in-drive) | a drive | `drive_id` |
| NTFS / SMB share | USN file reference number | a volume | `server` + `volume` |
| Local folder (MVP) | normalized absolute path | a source root | `root_id` |

- Uniqueness comes from the **inputs**, not the hash (sha256 collision is negligible). A coarse
  `source_id="onedrive"` WOULD collide across drives — pin the scope.
- Stability comes from using the source's **durable** id (Graph item id, USN file-ref). Local path is stable
  only if not renamed (rename = delete+new; acceptable for MVP).
- **Edge cases:** NTFS ref recycling after delete → safe because we drop the catalog row on delete, and
  content_hash mismatch forces reprocessing if a delete is ever missed. Same file copied to 2 locations →
  2 distinct file_ids → independently accounted for (desired). Cross-drive move → new drive_id → delete+new.

### Streaming & Performance (memory-bounded text, fast images)
Goal: cost ∝ chunk size (not file size) and high throughput — feeds NFR1 (throughput) and NFR4 (CPU/RAM per GB).

**Text — stream, never materialize the whole file:**
- **Chunked/streaming reads:** local files via `mmap` (OS pages on demand, no full-heap copy); remote via
  streamed download (`httpx stream=True`). `FileSource.open()` yields chunks lazily.
- **Sliding window with overlap:** carry an overlap tail (≈ max-entity-length, e.g. 256 chars) between chunks
  so a PII entity straddling a boundary is still caught; de-dupe findings by **global offset**.
- **Regex/checksum detectors** run natively on `chunk + overlap`.
- **NER without the memory hog:** segment into sentences/paragraphs and run `nlp.pipe(segments, batch_size=…)`
  — bounded memory, faster (batched), avoids spaCy `max_length` blowups.
- **Format-aware lazy extraction** (yield segments + location): PDF page-by-page (page = `location`);
  DOCX/XLSX via streaming XML / openpyxl read-only; logs/txt/csv line-by-line.
- **Incremental hashing:** `content_hash` updates over the same chunks — file never fully held to hash it.

**Images — fast vision path:**
- **Decode once, share** the array across YOLO + OCR + signature (no re-decode per detector).
- **Resize/letterbox to model input** (~640px) before inference; don't push full-res photos through.
- **Batch** image-modality files into one inference call (vectorized; routing already isolates the minority set).
- **Small variant + ONNX/OpenVINO INT8 export** (`model.export(format="openvino")`) for fast CPU inference
  (NFR4); YOLO26 NMS-free removes post-processing + tie-break nondeterminism.
- **Gate OCR** (the expensive step): skip tiny/icon images by size threshold; recognize only detected text
  regions; downscale first.
- **Process pool over files:** image decode + CPU detectors are independent per file → `multiprocessing`
  pool parallelizes (native libs release the GIL); same pool batches NER.

**Interface refinement (supersedes earlier `read()→bytes`):**
```
FileSource.iter_files() -> Iterator[ref]                 # metadata only (no content)
FileSource.open(ref)    -> stream                        # lazy chunks: local mmap / Graph streamed download
TextExtractor.segments(stream) -> Iterator[(text, base_offset)]   # page/sentence/line, lazy, offset-tracked
  → detectors run per segment with sliding-window overlap; global offsets build the finding `location`
  → content_hash updated incrementally over the same chunks
ImagePipeline: decode-once → resize → batched YOLO(ONNX/OpenVINO) → region-gated OCR → signature
```

## Implementation Patterns & Consistency Rules

### 🔒 GDPR Invariants (NON-NEGOTIABLE — every agent, every layer)
1. **Never persist or log a raw PII value.** Findings store enum + location + masked_snippet + scores only.
   Masking is applied at detection time, before anything is written or logged.
2. **Engine emits ONLY `machine_code`s present in `classification_enum`.** Adding a detector requires adding
   its enum row first (code + display_label + risk_weight + gdpr_focus). CI check enforces this.
3. **UI renders `display_label`, NEVER `machine_code`.** (`DE_SOZIALVERSICHERUNGSNR` → "German social
   security number".)
4. **Every finding and every remediation action writes an `audit_log` row** with detector_version,
   model_version, prompt_hash, timestamp. No silent state changes.
5. **DPO/admin responses contain aggregates only** — the API layer must never serialize owner-scoped
   finding detail to the admin role (structural enforcement of FR51/NFR13).
6. **Logs are PII-safe:** log file_id + classification_code + scores; never path contents or snippets at
   INFO. Structured JSON logs.

### Naming Patterns
- **Python:** snake_case (functions, vars, modules); PascalCase classes; Pydantic models suffixed `...Model`
  / `...Schema`. Detectors implement a common `Detector` protocol; named `<Attr>Detector`.
- **Database:** snake_case, plural tables (`findings`, `scan_catalog`); PK `id`; FKs `<entity>_id`;
  indexes `idx_<table>_<col>`. Enum codes UPPER_SNAKE (match pii-detection-scope.md exactly).
- **API:** REST, plural nouns (`/findings`, `/scans`); path params `{id}`; query params snake_case.
- **React/TS:** PascalCase components + `ComponentName.tsx`; hooks `useXxx`; non-component files kebab-case.

### Structure Patterns
- **Monorepo:** `/engine` (FastAPI app, detectors, scan workers, repositories), `/web` (React SPA),
  `/enum` (shared enum source of truth + generator), `/eval` (labeled set + harness), `/data` (SQLite + samples).
- **Engine layering:** `api/` (routers) → `services/` (orchestration) → `detectors/` (Tier-1/Tier-2) →
  `repositories/` (catalog access) → `models/` (Pydantic + DB). No layer skips downward.
- **Tests:** pytest in `engine/tests/` mirroring package paths; React tests co-located `*.test.tsx`.
- **Reproducibility test** lives at `eval/test_determinism.py` (run corpus 10×, diff Tier-1).

### Format Patterns
- **Wire format: snake_case JSON end-to-end** (Python-native; OpenAPI-generated TS client consumes as-is —
  no case-mapping layer).
- **Success envelope:** `{ "data": ..., "meta": {...} }`. **Error envelope:** `{ "error": { "code",
  "message", "detail" } }` with proper HTTP status.
- **Dates:** ISO-8601 UTC strings. **Booleans:** true/false.
- **IDs:** `file_id` = deterministic source-derived key (see File Identity below) — NEVER random.
  Internal record PKs (`finding`, `remediation_action`) = integer autoincrement for MVP; `audit_log` may
  use ULID (time-sortable) — switch to ULID/UUID for distributed edge workers in production. No random UUIDs in MVP.

### Communication Patterns
- Engine ↔ web communicate ONLY via the catalog/API — never direct calls into the scan process.
- Scan job lifecycle states: `queued → scanning → complete | failed` (catalog `scan_status`).
- Finding resolution states: `open → kept | deleted (soft) | escalated → resolved`.

### Process Patterns
- **Error handling:** detectors never throw into the scan loop — a detector failure logs + records a
  `detector_error` finding-stub and continues (one bad file never aborts a scan). Graph calls use
  retry+exponential backoff (NFR20).
- **Loading states:** TanStack Query (`isPending`/`isError`); query keys `['findings', ownerId]` etc.
- **Soft-delete:** `delete` sets `soft_delete_until = now + 14d`; a sweeper finalizes; recover before then.

### Enforcement
- CI: ruff + mypy (engine), eslint + tsc (web), enum-consistency check, determinism test.
- Pattern violations are PR blockers; enum/PII-logging rules are hard gates.

## Project Structure & Boundaries

### Complete Project Directory Structure
```
bosch-gdpr-discovery/
├── README.md
├── docker-compose.yml              # engine + web for one-command demo (stretch)
├── Makefile                        # make scan / make demo / make test
├── .github/workflows/ci.yml        # ruff+mypy, eslint+tsc, enum-check, determinism test
│
├── enum/                           # 🔒 SHARED single source of truth
│   ├── classification_enum.yaml    # machine_code, display_label, modality, mvp, risk_weight, gdpr_focus
│   └── generate.py                 # emits engine constants + TS types + SQL seed (one source → 3 outputs)
│
├── engine/                         # Python 3.12 — scan engine + FastAPI
│   ├── pyproject.toml              # uv-managed
│   ├── app/
│   │   ├── main.py                 # FastAPI entry; mounts routers; OpenAPI
│   │   ├── config.py               # settings, ruleset_version, model pins
│   │   ├── api/                    # routers (thin) — RBAC-gated
│   │   │   ├── findings.py         # FR28-30,35 owner queue
│   │   │   ├── actions.py          # FR31-34 keep/delete/escalate/recover
│   │   │   ├── escalations.py      # FR38-40 line-manager inbox
│   │   │   ├── admin.py            # FR42-45 aggregates only (NEVER per-file PII)
│   │   │   ├── scans.py            # FR23-27 trigger/progress
│   │   │   └── auth.py             # FR49-51 mock identity (MVP) / OIDC (prod)
│   │   ├── services/               # orchestration
│   │   │   ├── scan_orchestrator.py   # full+delta, dispatch (in-proc MVP)
│   │   │   ├── ownership.py            # FR21-22 fallback chain resolution
│   │   │   ├── scoring.py              # FR17-18 risk + confidence
│   │   │   └── escalation_policy.py    # 🔑 risk-tiered τ thresholds + budget governor
│   │   ├── detectors/              # FR6-16
│   │   │   ├── base.py             # Detector protocol; emits enum codes only
│   │   │   ├── tier1/              # text (Presidio), image (YOLO26, OCR)
│   │   │   └── tier2/              # LLM/VLM escalation (temp 0, pinned, prompt-hashed)
│   │   ├── sources/               # FR1-5b — pluggable file-source interface (the seam)
│   │   │   ├── base.py            # FileSource interface (iter_files, open→stream) + TextExtractor + ImagePipeline
│   │   │   ├── local_folder.py    # MVP primary (mmap streaming)
│   │   │   └── onedrive_graph.py  # MVP secondary (Graph /delta + streamed download)
│   │   ├── repositories/          # ONLY layer that touches the catalog
│   │   ├── models/                # Pydantic + DB schema
│   │   └── audit.py               # 🔒 append-only audit_log writer
│   └── tests/
│
├── web/                            # React + Vite + TS SPA
│   ├── package.json
│   └── src/
│       ├── routes/                 # role-gated route trees
│       │   ├── owner/              # FR28-36 queue, finding cards, 3 actions
│       │   ├── manager/            # FR38-40 escalation inbox
│       │   └── admin/              # FR42-45 KPI dashboard (aggregates)
│       ├── components/             # shared component library
│       ├── api/                    # generated typed client (from OpenAPI)
│       └── lib/                    # enum display labels (from enum/generate.py)
│
├── eval/                           # 🔑 the accuracy harness
│   ├── labeled_set/                # ~200 text entities + ~50 images, span/bbox ground truth
│   ├── run_eval.py                 # entity-level recall, stratified + severity-weighted
│   ├── calibration.py              # confidence-bin → precision curve (tunes τ)
│   └── test_determinism.py         # run corpus 10×, diff Tier-1 (NFR8)
│
└── data/
    ├── catalog.sqlite              # the spine (gitignored)
    └── samples/                    # a-klumpp synthetic data
```

### Architectural Boundaries
- **API boundary:** routers are thin; all logic in services; RBAC gate per endpoint; admin router
  physically cannot import owner finding-detail serializers (DPO-never-sees-PII, structural).
- **Catalog boundary:** ONLY `repositories/` reads/writes the catalog. Detectors and API never touch SQL.
- **Source boundary:** everything upstream of `FileSource.iter_files()/read()` is swappable; the engine
  knows nothing about OneDrive vs local (the seam that emulates the hybrid topology).
- **Enum boundary:** `enum/` generates engine constants, TS types, and SQL seed — no hand-copied lists.
- **Engine ↔ web boundary:** communicate ONLY via the API over the catalog; no shared process state.

### Requirements → Structure Mapping
| FR area | Location |
|---|---|
| FR1-5b Ingestion | `engine/app/sources/` |
| FR6-16 Detection | `engine/app/detectors/` (+ `enum/`) |
| FR17-22 Scoring/Findings/Ownership | `engine/app/services/{scoring,ownership}.py`, `repositories/` |
| FR23-27 Scan orchestration | `engine/app/services/scan_orchestrator.py`, `api/scans.py` |
| FR28-37 Owner remediation | `web/src/routes/owner/`, `engine/app/api/{findings,actions}.py` |
| FR38-40 Escalation | `web/src/routes/manager/`, `engine/app/api/escalations.py` |
| FR41-45 Admin/DPO | `web/src/routes/admin/`, `engine/app/api/admin.py` |
| FR46-51 Audit/compliance/access | `engine/app/audit.py`, `api/auth.py`, RBAC middleware |
| NFR6-9 Accuracy/reproducibility | `eval/` |

### Data Flow
source → modality router → Tier-1 detectors → (risk-tiered τ) → Tier-2 if uncertain → scoring →
repositories write **finding (enum+location+masked+scores, NO raw PII)** + **audit_log** → catalog →
API (RBAC-filtered) → role-gated SPA.

## Architecture Validation Results

### Coherence Validation ✅
- **Decision compatibility:** Python 3.12 + FastAPI 0.136 + Presidio 2.2 + YOLO26 + SQLite + React/Vite 8
  are mutually compatible (all current, May 2026). No contradictory decisions.
- **Pattern consistency:** snake_case end-to-end (DB→Python→JSON) removes case-mapping; enum-as-source-of-
  truth is enforced by `enum/generate.py` + CI; GDPR invariants align with the data model (no-raw-PII store).
- **Structure alignment:** layering (api→services→detectors/repositories) supports the decisions; the
  `FileSource` seam realizes the deployment-emulation decision; `repositories/`-only catalog access enforces
  the data boundary.

### Requirements Coverage Validation ✅
- **Functional (56 FRs):** every FR area maps to a concrete location (see Requirements→Structure table).
  Spot-check: FR24 delta → `scan_orchestrator` + catalog ruleset_version; FR51 DPO-no-PII → admin router
  cannot import owner serializers; FR46 audit → `audit.py`. No orphaned FRs.
- **Non-functional (22 NFRs):** NFR1-3 perf → throughput harness + in-proc/async; NFR4-5 → CPU Tier-1 +
  isolated Tier-2; NFR6-9 → `eval/` harness + risk-tiered τ; NFR10-14 → encryption + RBAC + append-only
  audit + no-PII store; NFR15-16 → hybrid topology + delta/catalog; NFR17-19 → plain-language SPA;
  NFR20-21 → Graph retry/backoff + notifications; NFR22 → article→control mapping.

### Implementation Readiness Validation ✅
- **Decisions:** all critical decisions documented with verified versions and rationale.
- **Structure:** complete tree with file-level specificity; boundaries explicit.
- **Patterns:** naming/format/communication/process patterns defined; GDPR invariants are hard gates.

### Gap Analysis Results
**Critical gaps:** None.
**Important gaps (address during build, non-blocking):**
- **Notifications service (FR36 — MVP):** in-app dashboard is covered, but the **Teams** delivery path
  has no dedicated module. Resolution: add `engine/app/services/notifications.py`; MVP may ship in-app
  only with Teams as a stretch (consistent with NFR21 channels).
- **WCAG 2.1 AA (NFR18):** not yet pinned to a component-library choice. Resolution: adopt an accessible
  primitive set (e.g. Radix/headless) in `web/src/components/` and add an a11y lint check.
**Nice-to-have gaps:**
- **At-rest encryption in MVP:** SQLite at-rest encryption (SQLCipher) deferred for the hackathon; prod
  Postgres uses native at-rest encryption (NFR10). Stated as a conscious MVP deferral.

### Architecture Completeness Checklist
**Requirements Analysis**
- [x] Project context thoroughly analyzed
- [x] Scale and complexity assessed
- [x] Technical constraints identified
- [x] Cross-cutting concerns mapped

**Architectural Decisions**
- [x] Critical decisions documented with versions
- [x] Technology stack fully specified
- [x] Integration patterns defined
- [x] Performance considerations addressed

**Implementation Patterns**
- [x] Naming conventions established
- [x] Structure patterns defined
- [x] Communication patterns specified
- [x] Process patterns documented

**Project Structure**
- [x] Complete directory structure defined
- [x] Component boundaries established
- [x] Integration points mapped
- [x] Requirements to structure mapping complete

### Architecture Readiness Assessment
**Overall Status:** READY WITH MINOR GAPS (all 16 checklist items met; no critical gaps; 2 important +
1 nice-to-have gap tracked above, all non-blocking for the build sequence).
**Confidence Level:** High.
**Key Strengths:** enum-as-single-source-of-truth; risk-tiered recall-first escalation with calibration;
findings-only/no-raw-PII data model; topology emulation via the FileSource seam; reproducibility as a
versioned mechanism; structural DPO-never-sees-PII enforcement.
**Areas for Future Enhancement:** Teams notifications, WCAG component baseline, SQLCipher/at-rest in MVP,
Postgres + Service Bus + edge workers (prod), video + P3.

### Implementation Handoff
**AI Agent Guidelines:** follow decisions exactly; treat GDPR invariants as hard gates; respect layer and
data boundaries; emit only enum codes.
**First Implementation Priority:** scaffold per Step 3 (uv init engine + create-vite web), build `enum/`
module + SQLite schema, then the vertical slice: local-folder text scan → one finding card → one owner action.
