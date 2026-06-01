# GDPR Data Discovery Tool

Scans local folders and OneDrive drives for GDPR-sensitive content — PII, document images, signatures — and surfaces findings through a role-gated React UI.

For architecture, module details, and data-flow diagrams see **[Systemdesign.md](Systemdesign.md)**.

---

## Stack

| Layer | Technology |
|---|---|
| Frontend | React 19 + Vite + Tailwind CSS |
| Backend | FastAPI + uvicorn |
| Detectors | Regex/Luhn, spaCy NER, YOLO11n ONNX, RapidOCR ONNX, Haar cascade |
| Tier-2 | OpenRouter LLM/VLM (optional, off by default) |
| Storage | SQLite (WAL mode) |
| File sources | Local folder, Microsoft OneDrive (Graph delta API) |

---

## Quick Start

### 1. Prerequisites

- Python 3.11+
- Node.js 18+
- (Optional) Azure app registration for OneDrive scanning
- (Optional) OpenRouter API key for Tier-2 LLM confirmation

### 2. Install dependencies

```bash
# Python
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -e ".[dev]"

# Node
cd web && npm install
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env — all variables are optional; the tool degrades gracefully when unset
```

### 4. Run

```powershell
# Starts FastAPI (:8000) + Vite dev server (:5173) in two terminal windows
.\launch.ps1
```

Or individually:

```bash
# Backend
uvicorn engine.app.main:app --reload --port 8000

# Frontend
cd web && npm run dev
```

Open `http://localhost:5173` — select **Owner** or **Admin** role.

---

## Common Commands

```bash
make dev          # launch.ps1 via PowerShell
make test         # pytest (engine + eval)
make eval         # run detector evaluation suite
make scan PATH=.  # one-off CLI scan of a folder
make enum         # regenerate enum artifacts from YAML
make lint-engine  # ruff + mypy on engine/
```

---

## Project Structure

```
engine/          FastAPI app + scan orchestrator + detectors
  app/
    api/         REST routers (scans, findings, aggregates, tier2)
    detectors/   text/, image/, tier2/, router.py
    services/    scoring, ownership, finding_write
    sources/     local_folder, onedrive_graph, onedrive_live
    repositories/catalog.py — sole SQLite access layer
web/             React SPA (admin + owner views)
enum/            classification_enum.yaml → Python/TS/SQL codegen
eval/            labeled corpus + detector evaluation harness
data/            catalog.sqlite, ML models (git-ignored)
config/          scan.yaml, escalation policy defaults
scripts/         run_scan.py, launch helpers
```

---

## Roles

| Role | Access |
|---|---|
| **Owner** | View findings for their files; masked snippets only |
| **Admin** | Launch scans, view KPI dashboard, manage all findings |
