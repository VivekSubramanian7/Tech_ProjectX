# Prior-Art Landscape — Sensitive Data Discovery (Bosch GDPR PoC)

Research captured 2026-05-30 to inform PRD + architecture. Not requirements — reference only.

## SCOPE CORRECTION (critical)
Target is **multi-modal unstructured data at rest, NOT source code.** HoundDog.ai is engine-design
inspiration only. We must handle:
- **Text docs** (.txt, Office, PDF, email) → text extraction + NER/regex/checksum (Presidio).
- **Images** (scans, screenshots, photos) → OCR for embedded PII text, PLUS face/person detection
  and signature detection (case study lists "Photo/video of a person" and "Signature" as personal data).
- **Video** → person/face detection on sampled frames.
P1 Scan Logic = a **pipeline that branches by file modality**, each feeding a common findings model.
Consequence: video + OCR make *scan speed* and *resource intensity* eval criteria much harder →
modality scope-tiering required for the 48h window.

## Reference tools

### HoundDog.ai (hounddogai/hounddog) — privacy CODE scanner
- Detects PII/financial/health data flows in source code (Python/JS/TS free; C#/Go/Java/SQL/GraphQL enterprise).
- **Deterministic static-analysis engine; AI used only to generate/update detection rules** (not at scan time).
- Local standalone binary — "code never leaves your machine." 1M+ LOC/sec. `--trace` for dataflow explainability.
- CLI + Markdown/HTML reports; enterprise emits RoPA/PIA/DPIA.
- **Lesson for us:** AI-offline / deterministic-at-scan = wins reproducibility + resource-intensity + speed. Local-only inference avoids the scanner itself being a GDPR risk.

### Microsoft Presidio (microsoft/presidio) — STRONGEST match for our task
- PII detection + anonymization over unstructured text/PDF/images and structured data.
- Analyzer (spaCy NER + regex + rule-based + checksums, confidence scores) → Anonymizer (mask/redact/encrypt).
- Runs locally / containers; Python/.NET/REST; fully extensible custom recognizers.
- **Likely engine core for P1 Scan Logic.**

### ReDiscovery (redglue/ReDiscovery)
- NER (MaxEnt) + dictionary + regex over documents and DBs; explicitly GDPR-oriented. Good architecture reference.

### Microsoft Purview — On-demand Classification (the BUY baseline / competitor)
- Native M365: scans SharePoint/OneDrive at rest using sensitive-info-types + regex; pre-built + custom classifiers.
- Pay-as-you-go (not in E5). Centralized compliance dashboard.
- **Threat to our pitch.** Must articulate why custom beats "just enable Purview": cost at 300k-OneDrive scale, custom per-user remediation UX, "Master of Data" attribution, tailored Bosch retention logic.

### Commercial UX references (for P3 Admin dashboard)
- Amazon Macie (S3, ML+pattern, findings dashboard), Nightfall (real-time SaaS DLP), Varonis (unstructured + access/insider-threat).

## Cascading detection architecture (user-defined)
Two independent per-finding scores:
- **Risk score** = legal severity (passport > phone; Art.9 > Art.4) → ranks owner queue.
- **Confidence score** = detection certainty → drives escalation.

Tiered detection:
- **Tier 1** deterministic (regex+checksum+NER+image detectors) on ALL files — cheap, fast, reproducible.
- **Tier 2** AI escalation ONLY for low-confidence cases: LLM for text, VLM for image/video.
Serves all 4 eval criteria: caps false negatives (FN = highest cost), keeps cost/speed low
(expensive model only on ambiguous minority). Tier-2 determinism must be engineered
(temp 0 / cached verdicts) to preserve reproducibility.

## Strategic implication
Case study leaves engine open ("AI / template-matching / hybrid — your call").
Prior art → **hybrid: deterministic detectors (regex + checksum + NER) at scan time; AI offline to generate/tune rules.**
Simultaneously serves 3 of 4 eval criteria: accuracy, reproducibility, resource-intensity (4th = speed, also helped by deterministic engine).

## Sources
- https://github.com/hounddogai/hounddog
- https://github.com/microsoft/presidio
- https://github.com/redglue/ReDiscovery
- https://learn.microsoft.com/en-us/purview/on-demand-classification
