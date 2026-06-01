# Bosch GDPR Data-Discovery Engine — System Design

---

## Feature & Design Highlights

| # | Feature / Principle | Description |
|---|---|---|
| 1 | **Torch-free ONNX runtime** | YOLO11n and OCR run entirely via `onnxruntime` + `rapidocr_onnxruntime`. `torch`, `ultralytics`, and `easyocr` are **never imported at runtime** — only used at build time to export `.onnx` weights. Cold-start drops from ~25 s → ~3-5 s. |
| 2 | **Modality-first routing** | Every file is classified as `TEXT`, `IMAGE`, or `OCR` before scanning begins. PDFs are sniffed via magic-byte probe (`/Font` vs `/Image`). This routes each file to exactly the right detector chain with zero wasted work. |
| 3 | **Two-pass image GDPR detection** | YOLO stage-1 detects coarse COCO classes (person, vehicle). A Haar cascade stage-2 confirms **face** inside a person box and **licence plate** inside a vehicle box. A bare torso is never surfaced — both detectors must agree. |
| 4 | **Deterministic write order** | Detection runs concurrently (bounded `ThreadPoolExecutor`), but DB writes happen on the main thread in fixed discovery order. Finding IDs are byte-identical run-to-run — reproducibility is a first-class property. |
| 5 | **Risk-tiered Tier-2 escalation** | Only low-confidence Tier-1 findings are escalated. The confidence threshold τ is **risk-gated**: Critical → 0.95, High → 0.90, Medium → 0.85, Low → 0.75. A per-run budget cap prevents runaway API spend. |
| 6 | **Ephemeral context only** | Tier-2 LLM/VLM receives only an in-memory snippet or cropped image bbox — the raw content is never written to disk or persisted in the catalog. All PII leaves the system masked. |
| 7 | **Delta scan with Graph token** | OneDrive sources support Microsoft Graph delta-link protocol. Only changed/created/deleted items are re-scanned; the delta token is stored per drive in SQLite for resumability. |
| 8 | **Non-blocking async API** | `POST /scans` returns a `scan_id` immediately; the scan runs on a daemon thread. `GET /scans/{id}` streams `current_file` + `phase` so the React dashboard shows live progress without polling the file system. |
| 9 | **Single image decode** | Image bytes are read once, hashed once, decoded once (Pillow). The resulting `DecodedImage` (raw RGB, width, height) is passed to YOLO, OCR, and Signature detectors — no redundant I/O. |
| 10 | **Offline-safe CI** | Every external dependency (ONNX model, OpenRouter API) has a deterministic in-process fallback. CI never hits the network; tests are reproducible without model weights. |
| 11 | **GDPR classification taxonomy** | 36 classification codes (20 MVP) covering Art. 5/17 identifiers through Art. 9 special-category data (biometric, health, genetic). Risk weights drive UI severity colours and Tier-2 thresholds. |
| 12 | **Role-gated React UI** | Admin and Owner roles enforced via `RbacGuard`. Admins control scans; Owners see only their files' aggregated KPIs. Raw PII values are never sent to the browser — only masked snippets. |

---

## High-Level Overview

Five layers communicate only through the REST API and the shared catalog — no raw PII crosses layer boundaries.

```mermaid
flowchart LR
    Users["Users<br/>Owner · Admin"]
    Web["Web SPA<br/>React + Vite"]
    API["FastAPI<br/>:8000"]
    Engine["Scan Engine<br/>orchestrator + detectors"]
    Catalog[("catalog.sqlite<br/>findings · scans · audit")]
    Sources["File Sources<br/>local · OneDrive"]

    Users --> Web
    Web -->|"/api proxy"| API
    API --> Engine
    Engine --> Catalog
    Engine --> Sources
    Sources -.->|stream files| Engine
```

| Layer | Path | Role |
|---|---|---|
| **Web** | `web/src/` | Role-gated UI; masked snippets only |
| **API** | `engine/app/api/` | Thin REST routers; async scan dispatch |
| **Engine** | `engine/app/services/` + `detectors/` | Scan, detect, score, write findings |
| **Catalog** | `data/catalog.sqlite` | Single store; enum + location + scores — no raw PII |
| **Sources** | `engine/app/sources/` | Pluggable ingestion (local walk / Graph delta) |

---

## System Architecture — Module Map

One level deeper than the overview: named modules and how they connect. Scan-step detail lives in the flow diagrams below.

```mermaid
flowchart TB
    subgraph UI["web/src — React SPA  :5173"]
        direction TB
        App["App.tsx · RoleSelect"]
        Owner["owner/OwnerPage<br/>FindingCard · ActionBar · DocumentViewer"]
        Admin["admin/AdminPage<br/>ScanLauncher · ScanProgress · KPI tiles"]
        Guard["RbacGuard · lib/rbac.tsx"]
        Client["lib/api.ts"]
    end

    subgraph REST["engine/app/api — FastAPI  :8000"]
        scans_r["scans.py"]
        findings_r["findings.py"]
        agg_r["aggregates.py"]
        tier2_r["tier2.py"]
    end

    subgraph Core["engine/app — orchestration & persistence"]
        Orch["scan_orchestrator.py<br/>daemon thread · delta · progress"]
        Router["detectors/router.py<br/>TEXT · IMAGE · OCR"]
        Score["services/scoring.py"]
        Own["services/ownership.py"]
        Write["services/finding_write.py"]
        Audit["audit.py"]
        Repo["repositories/catalog.py<br/>sole SQL access · WAL"]
        Identity["identity.py · file_id"]
    end

    subgraph Ingest["engine/app/sources — FileSource seam"]
        Base["base.py — FileRef · iter_files · open"]
        Local["local_folder.py"]
        Graph["onedrive_graph.py · graph_client.py"]
        Live["onedrive_live.py"]
    end

    subgraph TextMod["Text modules — detectors/text/"]
        Extract["extract.py<br/>PDF · DOCX · PPTX · plain"]
        PdfScan["pypdf PdfReader<br/>per-page text segments"]
        DocxScan["OOXML zip — word/document.xml"]
        PptxScan["OOXML zip — ppt/slides/*.xml"]
        Regex["regex_checksum.py<br/>36 patterns · Luhn · IBAN"]
        NER["ner.py<br/>rules-de · spaCy de_core_news_lg"]
        Merge["merge_detections_with_overlap"]
    end

    subgraph ImgMod["Image modules — detectors/image/"]
        Decode["_png.py · decode_image_once<br/>Pillow — single decode per file"]
        Yolo["yolo.py — YOLO11n ONNX<br/>onnxruntime · data/models/yolo11n.onnx"]
        Cascade["cascade.py — Haar stage-2<br/>face · licence plate"]
        OCR["ocr.py — RapidOCR ONNX<br/>det + rec · torch-free"]
        Sig["signature.py — ink-stroke heuristics"]
        Warmup["warmup.py · ml_status.py"]
    end

    subgraph T2Mod["Tier-2 — detectors/tier2/"]
        Policy["escalation_policy.py<br/>τ by risk · budget cap"]
        LLM["llm_text.py"]
        VLM["vlm_image.py"]
        ORClient["openrouter_client.py<br/>online · offline stub in CI"]
    end

    subgraph Shared["Shared artifacts"]
        Enum["enum/classification_enum.yaml<br/>→ Python · TS · SQL seed"]
        Models["data/models/yolo11n.onnx"]
        Eval["eval/run_eval.py · labeled corpus"]
    end

    subgraph DB["catalog.sqlite — WAL"]
        TCat["scan_catalog"]
        TFind["finding"]
        TRun["scan_run · audit_log"]
    end

    App --> Guard
    Owner --> Client
    Admin --> Client
    Client --> REST

    scans_r --> Orch
    findings_r --> Repo
    agg_r --> Repo
    tier2_r --> Orch

    Orch --> Router
    Orch --> Ingest
    Orch --> Score
    Orch --> Own
    Orch --> Write
    Orch --> Policy
    Orch --> Repo
    Write --> Audit

    Local --> Base
    Graph --> Base
    Live --> Base

    Router -->|TEXT / OCR| Extract
    Extract --> PdfScan
    Extract --> DocxScan
    Extract --> PptxScan
    Extract --> Regex
    Extract --> NER
    Regex --> Merge
    NER --> Merge
    Merge --> Score

    Router -->|IMAGE| Decode
    Decode --> Yolo
    Yolo --> Cascade
    Decode --> OCR
    Decode --> Sig
    OCR --> Regex
    Yolo --> Score
    Cascade --> Score
    Sig --> Score

    Policy --> LLM
    Policy --> VLM
    LLM --> ORClient
    VLM --> ORClient
    LLM --> Repo
    VLM --> Repo

    Repo --> DB
    Audit --> DB
    Enum -.-> TextMod
    Enum -.-> ImgMod
    Enum -.-> UI
    Models --> Yolo
    Warmup --> Yolo
    Warmup --> OCR
    Eval -.-> TextMod
    Eval -.-> ImgMod
```

### Module quick reference

| Module | File(s) | What it does |
|---|---|---|
| **Modality router** | `detectors/router.py` | Routes by extension; PDF gets 512-byte magic peek → TEXT or OCR |
| **PDF scanner** | `detectors/text/extract.py` + **pypdf** | Page-by-page text extraction; scanned PDFs fall through to OCR path |
| **DOCX / PPTX scanner** | `extract.py` | Stdlib OOXML zip parse — no external office libs |
| **Regex + checksum** | `regex_checksum.py` | EMAIL, IBAN, cards, passports, German IDs; Luhn/IBAN validation |
| **NER** | `ner.py` | PERSON_NAME, addresses; rules-de default, spaCy optional |
| **YOLO11n** | `yolo.py` + `yolo11n.onnx` | Stage-1 COCO coarse detect (person, vehicle); onnxruntime only at runtime |
| **Haar cascade** | `cascade.py` | Stage-2 face inside person box, plate inside vehicle box |
| **RapidOCR** | `ocr.py` | ONNX det+rec on image/PDF-OCR path; feeds regex over extracted text |
| **Signature** | `signature.py` | Heuristic ink-stroke detection → SIGNATURE enum |
| **Escalation policy** | `escalation_policy.py` | Risk-tiered τ (0.75–0.95) + per-run Tier-2 budget |
| **Tier-2 LLM/VLM** | `llm_text.py`, `vlm_image.py` | Ephemeral snippet/crop only; OpenRouter or deterministic stub |
| **Catalog repo** | `repositories/catalog.py` | Only layer that touches SQLite; delta tokens, findings, scans |
| **Ownership** | `ownership.py` | MVP path-prefix → owner mapping (`data/mock_owners.json`) |
| **OneDrive delta** | `onedrive_graph.py` | Graph `/delta` token stored per drive for incremental scans |
| **Enum taxonomy** | `enum/classification_enum.yaml` | 36 codes (20 MVP); drives detectors, UI labels, Tier-2 thresholds |

---

## Data Flow Summary

```mermaid
flowchart LR
    Src["FileSource"] --> Delta{"Delta<br/>pre-check"}
    Delta -->|skip| Skip["unchanged file"]
    Delta -->|process| Route["Modality Router"]
    Route --> T1["Tier-1 detectors"]
    T1 --> Sc["Scoring"]
    Sc --> Esc{"τ + budget"}
    Esc -->|low conf| T2["Tier-2 LLM/VLM"]
    Esc -->|ok| Write["finding_write"]
    T2 --> Write
    Write --> Cat[("catalog")]
    Cat --> API["FastAPI RBAC"]
    API --> SPA["React UI"]
```

---

## Scan Flow 1 — Text File (Tier-1 → Tier-2)

```mermaid
flowchart TD
    A([FileSource.iter_files]) --> B{is_scannable_path?}
    B -- no --> A
    B -- yes --> C[route_file\nextension lookup\nPDF: peek 512-byte magic]
    C --> D{Modality}
    D -- TEXT / OCR --> E

    E[extract_file\ndocx · pdf · pptx · csv · txt\nyield TextSegments + SHA-256 hash]

    E --> F[RegexChecksumDetector\n36 patterns — EMAIL · PHONE · IBAN\nCREDIT_CARD · PASSPORT · DE_STEUER_ID\nLuhn + IBAN checksum validation]
    E --> G[NerDetector\nrules-de: PERSON_NAME · HOME_ADDRESS\nTRAVEL_HISTORY · BILLING_ADDR\nor spaCy de_core_news_lg]

    F --> H[merge_detections_with_overlap\nresolve span conflicts by confidence]
    G --> H

    H --> I[final_scores — risk_score + confidence]
    I --> J[write_detection\nmasked_snippet only — no raw PII\nupsert scan_catalog status=complete]

    J --> K{EscalationPolicy\nconf < τ risk_weight?}
    K -- conf ≥ τ --> Z([DONE ✓])
    K -- conf < τ --> L[_slice_text_context\n±500 chars around span\nin-memory — never written]
    L --> M[run_tier2_text\nOpenRouter LLM  online\nor deterministic stub  offline/CI]
    M --> N[update_finding_tier2\ntier=2 · new confidence\nmodel_version · prompt_hash]
    N --> Z
```

---

## Scan Flow 2 — Image File — Double-Pass Person & Vehicle Detection

```mermaid
flowchart TD
    A([FileSource.iter_files]) --> B[route_file → Modality.IMAGE\n.png .jpg .jpeg .gif .webp .bmp .tiff]

    B --> C[Read file bytes ONCE\ndata = path.read_bytes\nhash = SHA-256 data\ndecoded = decode_bytes → DecodedImage\nwidth · height · raw RGB]

    C --> D[YoloDetector\nYOLO11n ONNX  Stage 1]
    C --> E[OcrDetector\nRapidOCR ONNX]
    C --> F[SignatureDetector\nink-stroke heuristics]

    subgraph YOLO["YOLO11n ONNX  —  Stage 1"]
        D --> G[letterbox → 640×640 NCHW float32]
        G --> H[onnxruntime InferenceSession\noutput 1×84×8400]
        H --> I[decode: cx cy w h + 80 class scores\nNMS  IoU≥0.45  conf≥0.25]
        I --> J{detected class}
    end

    subgraph PersonPath["Person Path  —  Stage 2"]
        J -- cls 0 person --> K[crop person_box from RGB]
        K --> L[Haar cascade detect_faces\nfrontalface_default.xml\nOpenCV CascadeClassifier]
        L --> M{face found\ninside person region?}
        M -- yes --> N[emit FACE\ncode=FACE  risk=High  Art.9 biometric\nconf = min 0.98  yolo_conf + 0.20\nTwo detectors agree → high certainty]
        M -- no --> O[DISCARD\nbare torso is not\nidentifying personal data]
    end

    subgraph VehiclePath["Vehicle Path  —  Stage 2"]
        J -- cls 2/3/5/7 vehicle --> P[crop vehicle_box from RGB\nCOCO: car · motorcycle · bus · truck]
        P --> Q[Haar cascade detect_plates\ncustom licence plate XML]
        Q --> R{plate found\ninside vehicle region?}
        R -- yes --> S[emit LICENSE_PLATE\ncode=LICENSE_PLATE  risk=Medium  Art.5/17\nconf = min 0.95  yolo_conf + 0.10]
        R -- no --> T[DISCARD\nvehicle only — no\nidentifiable plate]
    end

    subgraph OCRPath["OCR Path"]
        E --> U[downscale if > 1280px]
        U --> V[RapidOCR bundled ONNX\ndet + rec — no torch import\n→ extracted text lines]
        V --> W[RegexChecksumDetector\nover OCR text → text findings\nfrom image content]
    end

    F --> X[emit SIGNATURE\nrisk=High  Art.5/17/9-adj]

    N --> Y[write_image_detection × N\nbbox normalised 0–1\nmasked_snippet only\nupsert scan_catalog status=complete]
    S --> Y
    W --> Y
    X --> Y

    Y --> Z{EscalationPolicy\nconf < τ risk?}
    Z -- conf ≥ τ --> END([DONE ✓])
    Z -- conf < τ --> AA[_crop_image_bytes\nPillow bbox crop → PNG bytes\nin-memory — never persisted]
    AA --> AB[run_tier2_image\nOpenRouter VLM  online\nor deterministic stub  offline/CI]
    AB --> AC[update_finding_tier2\ntier=2 · new confidence\nmodel_version · prompt_hash]
    AC --> END
```

---

## Scan Flow 3 — Tier-1 → Tier-2 Escalation Policy

```mermaid
flowchart TD
    A[Tier-1 finding\nrisk_weight · confidence_score\nmodality · masked_snippet / bbox]

    A --> B{run budget\nexhausted?\ndefault cap = 100}
    B -- yes --> STOP([stop — queue remainder])
    B -- no --> C

    subgraph TAU["τ thresholds — EscalationPolicy"]
        T1[Critical → τ = 0.95]
        T2[High     → τ = 0.90]
        T3[Medium   → τ = 0.85]
        T4[Low      → τ = 0.75]
    end

    TAU -. lookup .-> C
    C{conf < τ risk_weight?}
    C -- conf ≥ τ --> DONE([keep Tier-1 result  DONE ✓])
    C -- conf < τ --> D{modality?}

    subgraph TextEsc["Text Escalation"]
        D -- text --> E[_slice_text_context\n±500 chars around span\nin-memory string only]
        E --> F[run_tier2_text\nOpenRouter mistral-7b-instruct  online\nOR deterministic stub  offline]
        F --> G[Tier2TextVerdict\nconfirmed · confidence\nmodel_version · prompt_hash]
    end

    subgraph ImgEsc["Image Escalation"]
        D -- image --> H[_crop_image_bytes\nPillow crop to finding bbox\nin-memory PNG bytes only]
        H --> I[run_tier2_image\nOpenRouter claude-3-haiku  online\nOR deterministic stub  offline]
        I --> J[Tier2ImageVerdict\nconfirmed · confidence\nmodel_version · prompt_hash]
    end

    G --> K[repo.update_finding_tier2\ntier = 2\nnew confidence_score\nmodel_version · prompt_hash sha256 16]
    J --> K
    K --> DONE2([finding updated  DONE ✓])
```

---

## Key Design Decisions

| Decision | Rationale |
|---|---|
| ONNX over PyTorch at runtime | Eliminates 16 s native-module cold-start on Windows; removes 2 GB torch wheel from production dependencies |
| Two-pass detection (YOLO → Haar) | Art. 9 applies to **biometric data**, not bodies. Face confirmation prevents false positives on background crowds, reducing owner alert fatigue |
| Separated detect / write phases | Concurrent detection + serial write = speed and deterministic finding IDs. Avoids SQLite write-lock contention under parallel workers |
| Ephemeral-only Tier-2 context | Context sent to LLM/VLM is never written to disk or stored in the DB. Satisfies GDPR data-minimisation for the tool itself |
| Delta token in SQLite | Persisting the Graph delta link means a restart resumes from the exact change cursor — no re-scan of unchanged files after a crash |
| Risk-tiered τ thresholds | Critical-risk PII (passport, credit card) requires near-certainty before bypassing Tier-2; Low-risk items tolerate more ambiguity, controlling API cost |
