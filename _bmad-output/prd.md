---
stepsCompleted: ['step-01-init', 'step-02-discovery', 'step-02b-vision', 'step-02c-executive-summary', 'step-03-success', 'step-04-journeys', 'step-05-domain', 'step-06-innovation', 'step-07-project-type', 'step-08-scoping', 'step-09-functional', 'step-10-nonfunctional', 'step-11-polish', 'step-12-complete']
completedDate: '2026-05-30'
inputDocuments:
  - 'C:/Users/vivek/Downloads/Case Study_GDPR_BOSCH.docx'
  - 'C:/Users/vivek/Downloads/Bosch Automated GDPR Compliance.pptx'
documentCounts:
  briefs: 0
  research: 0
  brainstorming: 0
  projectDocs: 2
classification:
  projectType: saas_b2b
  domain: data_privacy_gdpr_regtech
  complexity: high
  projectContext: greenfield
  deployment: internal_enterprise_tool_bosch_sso_scalable
planningPrinciple: 'Plan the full-fledged enterprise platform; tag requirements so hackathon MVP scope can be carved out cleanly in Step 8 (Scoping).'
scopeNote: 'Targets are MULTI-MODAL unstructured files at rest (text/docs, images, video) — NOT source code.'
piiScope: 'P1 = canonical 13 attributes from case study (must-detect); P2 = GDPR Art.4 general identifiers; P3 = GDPR Art.9 special categories (higher risk weight). Full catalog: _bmad-output/pii-detection-scope.md'
workflowType: 'prd'
releaseMode: phased
---

# Product Requirements Document - Automated GDPR Compliance (Bosch Data Discovery)

**Author:** Vivek
**Date:** 2026-05-30

## Executive Summary

Bosch holds personal data scattered across ~300,000 OneDrives and a globally distributed estate of SharePoint sites and file shares. Under GDPR, unaccounted and over-retained personal data is a direct liability — Article 83 caps fines at **4% of total worldwide annual revenue (~€3.6B for Bosch)**. Manual auditing at this scale is infeasible, and the knowledge required to judge whether a file is still lawfully needed lives with the **employee who owns it**, not with any central team or IT function.

This product is a Bosch-built **GDPR accountability engine**: a cost-effective, high-speed platform that scans **multi-modal unstructured files** (text/documents, images, video) at rest, detects the full canonical set of personal-data attributes, scores each finding by legal risk, and routes a plain-language recommendation to the **data-owning employee** to justify-and-keep or delete. Every action produces a reproducible, regulator-defensible record. The engine runs on a two-stage cadence — a **full scan** followed by **delta scans** of changed files only — keeping continuous operation economically viable at Bosch scale.

The target end-state is not "delete files" but **"every personal-data file is accounted for"** — either justified-and-retained or removed — converting an impossible centralized audit into thousands of trivial, owner-level decisions.

### What Makes This Special

- **Speed + cost as the headline.** Fast and cheap enough to scan continuously across 300k+ drives, where commercial pay-as-you-go tools (Microsoft Purview on-demand, Varonis) become economically painful at this scale. Cheap scanning is what makes continuous compliance — and therefore real risk reduction — possible.
- **Owner-decides, not IT.** Findings route to the employee who actually knows the document's purpose. IT and admins explicitly do **not** carry the per-file accountability decision; they get oversight and aggregate reporting only.
- **Risk-scoring that ranks but never hides.** Each finding carries a legal-severity score that orders the employee's queue (high-weight files first) — but **no finding is suppressed**, preserving the "fully accounted for" guarantee.
- **Multi-modal detection.** Text *and* images (OCR, faces, signatures) *and* video — beyond the text-only ceiling of most tools.
- **Tiered, full-coverage detection scope.** Detects the **13 canonical PII attributes** from the case study (Priority 1, must-detect), extensible to GDPR Art. 4 general identifiers (P2) and Art. 9 special categories (P3) — where special-category data (health, biometric, etc.) automatically carries higher risk weight. Full catalog in `pii-detection-scope.md`.
- **Deterministic, reproducible engine.** Repeatable results that are defensible to a regulator; AI is used to generate and tune detection rules, not to gamble at scan time.
- **Build, not buy — by necessity.** The scanner touches PII, so it cannot ship data to a third party (data sovereignty); the justification loop must fit Bosch's own identity, org structure ("Master of Data" attribution), and retention rules. This is an architectural requirement, not a preference.
- **GDPR principles designed into the flow, not shown as jargon.** Art. 5 (minimisation/storage-limitation), Art. 17 (erasure), Art. 25 (privacy-by-design), Art. 32 (security) shape the UI and end-to-end workflow; the employee sees only plain language.

## Project Classification

- **Project Type:** SaaS B2B — internal enterprise data-governance platform (scan engine + per-user view + admin dashboard + source connectors)
- **Domain:** Data Privacy / GDPR Compliance (RegTech)
- **Complexity:** High — hard regulatory constraint, multi-modal AI, reproducibility/accuracy pressure, and 300k-drive scale
- **Project Context:** Greenfield. Planned as the full enterprise platform; the 48-hour hackathon MVP will be carved out as an explicit scope slice (Step 8), with every requirement tagged for clean separation.

## Success Criteria

### User Success
- **90% of findings resolved in under 60 seconds**; the remaining ambiguous ~10% **escalated within 24 hours**.
- **Zero GDPR expertise required** — no article numbers or "data subject/controller" jargon in the UI; plain verbs ("Delete this file", not "Initiate erasure"). A plain-language pass is required on every UI string.
- **Three first-class actions**, not two: **Keep (justify)** · **Delete** · **"I'm not sure — escalate"** (routes to a team lead / data steward, *not* IT, with a deadline). Prevents uncertain owners defaulting to "keep".
- **Deletion feels safe:** soft-delete / grace period ("scheduled for deletion in 14 days — cancel anytime"). Keeping requires slightly more effort than deleting — the behavioral nudge that actually shrinks the data footprint.
- **Confidence shown as a simple signal** ("likely" / "not sure"), never a raw percentage. The ranked queue is ordered silently by risk with progress framing ("3 of 47 done"); the raw risk score is not shown to the employee.
- Each finding carries a **plain-language consequence hint** (e.g. "passport numbers are sensitive personal data — keeping them without a business reason creates legal exposure for Bosch").

### Business Success
- **Coverage:** % of Bosch's drive estate scanned and accounted for (path to 100% of OneDrives + SharePoint + file shares).
- **Risk reduction:** measurable decline in unaccounted / over-retained personal-data files — the metric that shrinks the ~€3.6B GDPR Art. 83 exposure.
- **Remediation rate:** % of high-risk findings resolved by owners within an SLA (roadmap target: 80% of high-risk findings actioned within 30 days).
- **Cost efficiency:** cost per TB scanned materially below Microsoft Purview on-demand / Varonis PAYG at 300k-drive scale — the build-vs-buy proof.

### Technical Success (measurable, ground-truth-anchored)
- **A labeled evaluation set is a prerequisite, not an afterthought** — span/bounding-box-level ground truth, with label provenance and inter-annotator agreement. Recall claims are meaningless without it. (The `a-klumpp/GDPR-data-samples` repo is a starting point, not the test suite.)
- **Entity-level recall** (not per-file), **stratified by PII category and modality**, and **severity-weighted** — top-severity (Art. 9) recall is gated separately so easy wins (emails) cannot mask catastrophic misses (e.g. health data).
- **False negatives are the highest-cost error** (a missed PII attribute = undetected legal liability). The engine biases toward **recall**, tolerating a higher false-positive rate because the owner-review step filters false positives cheaply.
- **Tier-1 detectors: 100% deterministic** (verified by running the corpus 10× and diffing). **Tier-2 AI: documented as non-deterministic**, handled via temperature-0 + pinned model/version + an **immutable per-finding audit log** (detector version, model version, prompt hash, timestamp).
- **Confidence calibration:** a calibration curve (confidence bins vs. actual precision) is produced, or the gap is named explicitly.

### Measurable Outcomes (PoC commitments)
| Metric | Method | PoC threshold |
|---|---|---|
| Entity-level recall, P1, text | labeled eval set (≥200 entities) | **≥90%** |
| Entity-level recall, P1, image | labeled set (≥50 images) | **≥80%** (image is harder) |
| Top-severity (Art. 9) recall | severity-stratified eval | gated separately, highest bar |
| False-positive rate, text | labeled negative corpus | ≤25% (human-filtered) |
| Determinism, Tier-1 | run corpus 10×, diff | 100% identical |
| Determinism, Tier-2 | documented + audit log | log, don't claim |
| Throughput | 1 GB mixed corpus, demo HW, median of 3 runs | baseline TBD on HW |
| Eval-set provenance | inter-annotator agreement | Cohen's κ ≥ 0.8 |

> **Production / vision targets** (≥95–99% recall, 100% estate coverage, 80% remediation SLA, order-of-magnitude cheaper than Purview/Varonis) are **roadmap items**, not claimed for the PoC.

## Product Scope

> This is the high-level scope overview. See **Project Scoping & Phased Development** for the authoritative MVP strategy, source design, resourcing, and risk ladder.

### MVP — Minimum Viable Product
- **Sources:** local folder (PRIMARY) + OneDrive via Microsoft Graph (SECONDARY), behind one pluggable file-source interface.
- Scan engine detecting **Priority-1 attributes across BOTH text and image** (locale: **Germany-first**):
  - **Text:** NER + regex + checksum — names, username, email, phone, fax, home/billing addresses, passport no., ID card no. (DE), driver's licence no., IBAN, credit-card PAN, IP address, employee ID (pending Bosch format), German social security no., German Tax-ID; travel history best-effort via LLM.
  - **Image:** OCR (text PII inside images) + face/person detection + license-plate detection + signature detection.
- **Cascading detection:** deterministic Tier-1 on all files; **LLM (text) / VLM (image) Tier-2 escalation** only on low-confidence findings.
- **Risk score + confidence score** per finding; ranked queue, **nothing hidden**.
- **User View:** per-owner findings list + three guided actions (keep / delete / escalate) + soft-delete.
- **Admin View:** KPI dashboard — total files scanned, total data volume (GB/TB), findings count, scan progress.
- **Full scan + delta scan**; deterministic, reproducible Tier-1.
- **A labeled evaluation set** — the harness for proving accuracy — as an explicit MVP deliverable.

### Growth Features (Post-MVP)
- Video modality (capped frame-sampling); Priority-2 semantic attributes; non-DE locales.
- **SharePoint + file-share connectors** (case-study Priority 4; OneDrive ships in MVP).
- "Master of Data" ownership resolution on shared sources; retention automation (3-year rule); remediation SLAs + automated reminders.

### Vision (Future)
- Priority-3 special-category detection with elevated risk weighting.
- Continuous, autonomous scanning across the full 300k-drive estate.
- Regulator-ready reporting (RoPA / DPIA-style exports); full audit lineage; org-structure-aware routing.

## User Journeys

Personas are Germany-first, reflecting Bosch. Scanning is automated; there is no separate human scan-operator journey.

### Journey 1 — Lena, the Data Owner (happy path)
**Persona:** Lena Vogt, 34, a project engineer in Stuttgart. Organized, busy, no GDPR training. ~8,000 files in her OneDrive accumulated over 5 years.

- **Opening:** Lena receives a calm notification — *"3 of your files may contain personal data. ~2 minutes to review."* A manageable nudge, not a scary compliance alert.
- **Rising action:** She opens her view to a clean queue ("Start here"). Top item: *"This file contains a passport number — likely. Keeping passport numbers without a business reason creates legal exposure for Bosch."* She recognizes an old onboarding scan she no longer needs.
- **Climax:** She clicks **Delete**. The system responds *"Scheduled for deletion in 14 days — cancel anytime."* Reversible, so no fear.
- **Resolution:** Next is a contract she needs; she clicks **Keep**, picks a dropdown reason ("Active contract — legal/business need"). Queue shows "3 of 3 — all clear." Under 90 seconds. She feels competent, not policed.

*Reveals:* notification system; per-owner ranked queue; plain-language finding cards (consequence hint + confidence signal); one-click delete with soft-delete/grace period; keep-with-reason (dropdown, not free text); progress framing.

### Journey 2 — Lena, the uncertain owner (edge case)
- **Opening:** One flagged file is a spreadsheet from Thomas, a colleague who left 18 months ago, in a shared folder Lena now owns.
- **Rising action:** It holds employee IDs and home addresses. Lena can't judge whether it's still needed — it's not really "hers."
- **Climax:** Rather than defaulting to "keep" out of fear, she clicks **"I'm not sure — escalate"** and picks a reason ("Not my data / former colleague's file").
- **Resolution:** It routes to her **line manager (or assigned delegate)** with a deadline. Her queue clears; responsibility moves to someone who can decide. She isn't penalized for not knowing.

*Reveals:* third action (escalate) with reason capture; escalation routing to line manager/delegate (not IT) with SLA/deadline; ownership-ambiguity handling; finding leaves owner's queue but stays accounted for.

### Journey 3 — Markus, the Line Manager / assigned delegate (escalation handler)
**Persona:** Markus Bauer, 45, team lead designated to handle his department's escalations. Practical, wants to clear his plate efficiently.

- **Opening:** Markus sees a small "Escalations" queue — files his reports couldn't judge, including Thomas's spreadsheet.
- **Rising action:** He has context Lena lacked: the spreadsheet fed a project that closed; retention has lapsed.
- **Climax:** He confirms **Delete** on behalf of the orphaned data, with a justification logged.
- **Resolution:** The finding is resolved and auditable. Departed-employee data — the classic compliance black hole — actually got handled.

*Reveals:* line-manager/delegate role + escalation inbox; act-on-behalf with logged justification; ownership reassignment for orphaned/departed-employee data; audit trail of who decided and why.

### Journey 4 — Dr. Hofmann, the DPO / Admin (oversight)
**Persona:** Dr. Anja Hofmann, Data Protection Officer, accountable to the board and regulators. Does **not** want to review individual files — she wants the picture and the proof.

- **Opening:** She opens the admin dashboard: total files scanned, total volume (TB), findings count, scan progress across the estate.
- **Rising action:** She sees trends — findings dropping as owners remediate, which departments lag, coverage climbing.
- **Climax:** A regulator asks "show me you're managing personal data." She exports an aggregate report backed by the immutable audit trail — reproducible evidence, not a promise.
- **Resolution:** Defensible oversight without ever touching an employee's file. Accountability is distributed; her job is governance, not triage.

*Reveals:* admin KPI dashboard (files/volume/findings/progress); trend analytics + coverage by org unit; regulator-ready export backed by audit log; strict separation — admin sees aggregates, never per-file decisions.

### Journey Requirements Summary
| Capability area | Driven by |
|---|---|
| Scan engine (full + delta, multi-modal, cascading detection) | All journeys |
| Notification / alerting | J1, J2 |
| Per-owner ranked queue + finding cards (plain language, consequence hint, confidence signal) | J1, J2 |
| Three actions: keep-with-reason / delete (soft-delete) / escalate | J1, J2 |
| Escalation routing + line-manager/delegate inbox + act-on-behalf | J2, J3 |
| Ownership resolution (incl. departed-employee / orphaned data) | J2, J3 |
| Admin/DPO KPI dashboard + trends + coverage | J4 |
| Audit trail + regulator-ready export | J3, J4 |
| Role-based access (owner / line-manager / admin separation) | All |

## Domain-Specific Requirements

### Compliance & Regulatory
- **GDPR is the governing regulation.** The product is designed around four articles (as scaffolding, not UI jargon):
  - **Art. 5** (data minimisation & storage-limitation) → the scan-and-account model + retention enforcement (3-year default rule from the case study).
  - **Art. 17** (right to erasure) → the delete action and its auditable confirmation flow.
  - **Art. 25** (data protection by design & by default) → human-in-the-loop, owner-decides, local inference, least-privilege access — built in, not bolted on.
  - **Art. 32** (security of processing) → encryption, access control, and the audit trail.
- **Art. 9 special-category data** carries elevated legal risk weight (detection deferred to Vision, but the risk-scoring model reserves its top tier for it).
- **Art. 83 accountability:** the ~€3.6B (4% of revenue) fine ceiling is the business case; the audit trail is the evidence of active management shown to a regulator.
- **Art. 5(2) accountability** has a long shelf life → audit records retained well beyond a single scan cycle.

### Technical Constraints
- **Data sovereignty (hard constraint):** the scanner reads PII, so data and inference stay inside the Bosch perimeter. **No PII may be sent to third-party/external AI services.** Tier-2 LLM/VLM must be self-hosted / local.
- **Reproducibility as a legal property:** Tier-1 fully deterministic; Tier-2 via temperature-0 + pinned model versions + an immutable per-finding audit log (detector version, model version, prompt hash, timestamp).
- **Security:** encryption in transit and at rest for the catalog and findings store; least-privilege, role-segregated access (owner / line-manager / admin). The findings store is itself sensitive (a map of where PII lives) and must be hardened accordingly.
- **Privacy-by-design in the tool itself:** the system minimizes what it stores — findings reference locations and attribute types, not copies of PII values; any PII cached for Tier-2 is ephemeral.
- **Performance:** continuous operation at 300k-drive scale; delta scans dramatically cheaper than full scans; resource footprint low enough to avoid dedicated heavy infrastructure.

### Integration Requirements
- **Microsoft 365 estate:** OneDrive + SharePoint via **Microsoft Graph API** (incl. `/delta` for incremental change feeds).
- **File shares:** SMB/NTFS access; **USN Change Journal** for delta detection.
- **Identity:** Bosch corporate **SSO / Entra ID (Azure AD)** for authentication; **AD/Entra org graph** for ownership resolution and line-manager routing.
- **Notification channels:** **in-app user dashboard + Microsoft Teams message** (primary) for owner nudges and escalation alerts; email optional/fallback.

### Findings Data Model (classification enum)
- Each finding is stored with a **controlled-vocabulary classification tag (enum)** — **not the raw PII value**.
- Each classification carries a **machine enum code** (stable key for storage, aggregation, reporting) **and a human-readable display label** (what the UI shows). The UI never exposes the raw enum code — e.g. `DE_SOZIALVERSICHERUNGSNR` renders as "German social security number". The catalog also stores each classification's **risk weight** and design-time **GDPR-principle mapping**.
- A finding record holds: **location + classification enum + risk score + confidence score** (no raw PII value).
- **Aggregation:** the enum is the roll-up key for the admin/DPO dashboard (counts and trends by attribute type, sliceable by org unit) and for regulator-ready reporting.
- **Context without honeypot:** the owner sees the display label + a **masked snippet or location pointer** (e.g. "passport number on page 2, •••••4521"), never a persisted raw value.
- The enum is the canonical PII attribute catalog (`pii-detection-scope.md`) promoted to a single source of truth used by detectors, UI labels, risk weights, and reporting.

### Risk Mitigations
| Risk | Mitigation |
|---|---|
| **False negatives** (undetected PII = liability) | Recall-biased engine + Tier-2 AI escalation net + labeled eval set to measure |
| **Scanner becomes a PII honeypot** (findings store maps all PII) | Store locations/classification enums not values; encrypt + harden + least-privilege; ephemeral Tier-2 caching |
| **Data leaves perimeter via external AI** | Self-hosted LLM/VLM only; hard architectural prohibition |
| **Ownership misrouting** (wrong person / void) | Ownership-resolution policy with fallback chain (owner → line manager → assigned delegate); orphaned/departed-employee handling |
| **Indefensible findings** (can't reproduce why flagged) | Deterministic Tier-1 + immutable audit log + detector/model versioning |
| **Stale clearances** (file cleared under old rules) | Delta-scan ruleset-version invalidation forces re-evaluation |
| **Employee fear/avoidance** → keep-everything | Soft-delete, "I'm not sure" escalation, plain-language, no blame |

## Innovation & Novel Patterns

### Detected Innovation Areas
1. **Cascading deterministic → AI escalation engine.** Tier-1 deterministic detectors run on everything (cheap, fast, 100% reproducible); only low-confidence findings escalate to a local LLM/VLM. Most tools are *either* pattern-based (HoundDog, classic DLP) *or* ML-based (cloud PII APIs). Doing both — with AI reserved as a recall safety-net for the ambiguous minority — is what makes recall-first compliance affordable at 300k-drive scale. **"The AI is the safety net, not the engine."**
2. **Dual independent scoring (risk × confidence).** Separating *legal severity* (ranks the queue) from *detection certainty* (drives escalation) is uncommon — most scanners emit a single confidence number. Two orthogonal axes let us prioritize what matters legally while routing only the uncertain to expensive AI.
3. **Accountability routing as the product (not detection).** The reframe: this is not a scanner with a dashboard, it is a **workflow-automation system that distributes a legal decision to the person who can actually make it** (the data owner), with line-manager escalation for ambiguous and orphaned cases. Detection is plumbing; routing of justification is the innovation.
4. **Multi-modal detection with in-perimeter inference.** Text + image (OCR + face + plate + signature) + (future) video, with *local* LLM/VLM — the scanner never leaks PII to external services. Privacy-preserving AI on the data itself.
5. **Privacy-by-design findings model.** Storing classification enums + locations, never raw PII values, so the compliance tool does not itself become the company's largest PII honeypot.

### Market Context & Competitive Landscape
- **Microsoft Purview (on-demand classification):** native to M365 but admin-centric, pay-as-you-go (expensive at 300k-drive scale), no per-owner remediation workflow. Our wedge: cost + owner-decides UX.
- **Varonis / Amazon Macie / Nightfall:** strong detection + dashboards, but central-console models; not designed to distribute the *decision* to thousands of owners cheaply.
- **HoundDog.ai:** deterministic-first philosophy we admire — but it scans *code*, not unstructured documents/images.
- **Microsoft Presidio (OSS):** likely engine building block, not a product. We compose it into a workflow.
- **The gap we fill:** nobody combines cheap continuous multi-modal scanning + owner-distributed accountability + in-perimeter AI + reproducible audit trail in one in-house tool.

### Validation Approach
- **Detection quality:** the labeled evaluation set (entity-level, severity-stratified recall) proves the cascading engine catches what matters.
- **Escalation economics:** measure the % of files needing Tier-2 AI; the innovation only holds if that fraction stays small (validates the cost claim).
- **Workflow validation:** test the owner → escalate → line-manager flow on the demo personas; confirm uncertain files do not dead-end.
- **Reproducibility proof:** run the corpus 10× and diff — demonstrates the deterministic Tier-1 claim live.

### Risk Mitigation
| Innovation risk | Fallback / mitigation |
|---|---|
| Tier-2 escalation fraction too high → cost blows up | Tune confidence threshold; tighten Tier-1 detectors; cap Tier-2 budget per run |
| Local LLM/VLM too heavy for "low resource" claim | Quantized/smaller models; escalate only on the genuinely ambiguous; batch off-peak |
| Tier-2 non-determinism undermines reproducibility | Temp-0, pinned versions, cached verdicts, full audit log |
| "Owner-decides" fails if ownership can't be resolved | Fallback chain (owner → line manager → assigned delegate); orphaned-data handling |
| Dual-score UX confuses users | Risk hidden (silent ranking); confidence shown as simple signal, never a number |

## SaaS B2B Specific Requirements

### Project-Type Overview
An **internal, single-organization enterprise tool** for Bosch — not a commercial multi-tenant SaaS and not subscription-based. "Tenancy" means a single Bosch tenant, scaled across departments/org-units and a global drive estate. Authentication is corporate SSO (Entra ID); no public sign-up, no billing tier.

### Tenancy Model
- **Single-tenant (Bosch), org-unit-aware.** One logical tenant; data and findings partitioned and filterable by department/org-unit (for dashboards, coverage, routing) via the Entra/AD org graph.
- Architected to **scale horizontally** across the 300k-drive estate, not to isolate multiple customers.
- *Subscription tiers: N/A — internal tool (section skipped per project type).*

### RBAC Matrix
| Capability | Data Owner (employee) | Line Manager / Delegate | Admin / DPO |
|---|---|---|---|
| See **own** flagged files | ✅ | ✅ (own) | ❌ |
| Act on own files (keep / delete / escalate) | ✅ | ✅ (own) | ❌ |
| See **team's escalated** files | ❌ | ✅ (their reports only) | ❌ |
| Act on escalations (on behalf, logged) | ❌ | ✅ | ❌ |
| Reassign ownership (orphaned/departed) | ❌ | ✅ | ✅ |
| View **aggregate** KPI dashboard | ❌ | ✅ (team scope) | ✅ (estate-wide) |
| View per-file PII content | own only | own + escalated | ❌ **never** |
| Configure scans / sources / detectors | ❌ | ❌ | ✅ |
| Export regulator-ready / audit reports | ❌ | ❌ | ✅ |
| Access audit log | ❌ | own actions | ✅ (full) |

**Design principle enforced by the matrix:** the **DPO/Admin never sees individual PII or makes per-file decisions** — only aggregates and governance. Accountability stays with the owner, encoded as access control (also an Art. 32 / least-privilege measure). No break-glass per-file drill-down.

### Integrations
Microsoft Graph (OneDrive/SharePoint + `/delta`), SMB/NTFS + USN journal (file shares), Entra ID SSO + org graph (auth + routing), Microsoft Teams + in-app dashboard (notifications). See Domain-Specific Requirements for detail.

### Compliance
GDPR Art. 5/17/25/32; data sovereignty / in-perimeter inference; reproducibility + immutable audit log; privacy-by-design findings model (enums, not raw values). See Domain-Specific Requirements.

### Implementation Considerations
- **Scan orchestration** is a background service (automated), independent of the user-facing web app — they communicate via the findings store.
- **Three frontend surfaces** map to the three roles: User View, Line-Manager/Escalation View, Admin/DPO Dashboard — sharing one component library, gated by RBAC.
- **Org-graph dependency:** routing and dashboards rely on accurate Entra/AD manager relationships; stale org data is an operational risk (mitigation: nightly sync + fallback to assigned delegate).

## Project Scoping & Phased Development

### MVP Strategy & Philosophy
- **Approach:** *Problem-solving MVP* — prove the core bet (cheap, reproducible, multi-modal detection + owner-routing) end-to-end in 48 hours.
- **Source design:** a **pluggable, source-agnostic file-source interface** with two MVP implementations — **(1) local folder (PRIMARY, demo backbone, built first); (2) OneDrive via Microsoft Graph (SECONDARY, live-integration showcase).** SharePoint + file shares are additional implementations deferred to Growth.
- **Deployment:** MVP = a **single local app** (one process). **Production topology is left open for the Architect** (see Architecture open questions) — the clean file-source interface keeps that decision deferrable.
- **Demo-data nuance:** the `a-klumpp/GDPR-data-samples` set is synthetic/public, not real Bosch PII — so for the **hackathon demo only**, a hosted LLM/VLM is acceptable for Tier-2. The **production** data-sovereignty rule (in-perimeter inference) remains in the architecture; the distinction is stated explicitly.
- **Resource requirements (hackathon team ~4):** 1–2 backend/ML (scan engine + detectors), 1 frontend (3 role views), 1 data/integration (SQLite catalog + labeled eval set + Graph/OneDrive auth — start Hour 1, it is the long pole).

### MVP Feature Set (Phase 1 — 48h)
**Core journeys:** J1 (owner happy path), J2 (escalate), J4 (admin dashboard); J3 (line-manager) partial (escalations land in a queue).

**Must-have capabilities:**
- **Sources:** local folder (primary) + OneDrive via Graph (secondary), behind one file-source interface.
- **P1 — Cascading scan engine:** Tier-1 deterministic detectors across **text + image** (MVP attribute set); **YOLO (Ultralytics)** for face + license-plate + person (Tier-1, deterministic) + **OCR** for text-in-images/plate numbers; Tier-2 **LLM/VLM** escalation on low-confidence. Risk + confidence score per finding; classification enum + masked snippet.
- **Full scan + delta scan** via SQLite catalog (incl. ruleset-version invalidation demo).
- **P2 — User View:** per-owner ranked queue, plain-language cards, three actions (keep-with-reason / soft-delete / escalate), confidence as simple signal, progress framing.
- **P3 — Admin View:** KPI dashboard (files scanned, data volume, findings count, scan progress) + aggregation by classification enum.
- **Labeled evaluation set** (~200 text entities + ~50 images) for entity-level recall / FP.
- **Reproducibility demo:** run twice, identical Tier-1 output.

### Post-MVP Features
**Phase 2 (Growth):** SharePoint + file-share connectors; video modality (capped); local/self-hosted Tier-2 inference; full SSO + RBAC enforcement; "Master of Data" ownership resolution at scale; P2 semantic attributes + non-DE locales; retention automation (3-yr), SLAs, reminders; RetinaFace Tier-2 face fallback; distributed/edge deployment topology.

**Phase 3 (Vision):** P3 special-category (Art. 9) detection; continuous autonomous estate-wide scanning; regulator-ready exports (RoPA/DPIA); full audit lineage; org-aware routing.

### Risk Mitigation Strategy
- **Technical risk — image detection is the hardest part in 48h.** Mitigation: pretrained off-the-shelf models (YOLO for face/plate/person; OCR via EasyOCR/Tesseract). **Image de-scope ladder if behind:** keep OCR + YOLO-face → drop license-plate → drop signature. Image must not block text.
- **Technical risk — OneDrive/Graph OAuth is the long pole.** Mitigation: spike it in the first hours; **local-folder (primary) is the guaranteed-working fallback** so a failed OAuth never kills the demo.
- **Technical risk — Tier-2 in 48h.** Mitigation: hosted LLM/VLM on synthetic sample data for the demo; threshold tuned so few files escalate.
- **Resource/time risk — too ambitious.** Mitigation: build the vertical slice first (local-folder text scan → one finding card → one action), then widen. **Cut order if behind:** SharePoint/shares (already out) → delta via Graph (fall back to full scan) → image detectors (per ladder) → admin polish. **Never cut:** local-folder text scan + one working owner action + reproducibility.
- **Validation risk — "is it accurate?"** Mitigation: the labeled eval set gives a real number, not a claim.

## Functional Requirements

Each FR is tagged by phase `[MVP]` / `[Growth]` / `[Vision]`. FRs state capabilities (what), not implementation (how). This is the binding capability contract.

### Data Source Ingestion
- **FR1:** The system can ingest files from a local folder source. `[MVP]`
- **FR2:** The system can ingest files from a user's OneDrive. `[MVP]`
- **FR3:** The system can ingest files from SharePoint sites. `[Growth]`
- **FR4:** The system can ingest files from network file shares. `[Growth]`
- **FR5:** The system can read text documents. `[MVP]`
- **FR5a:** The system can read images. `[MVP]`
- **FR5b:** The system can read video. `[Growth]`

### Detection & Classification
- **FR6:** The system can detect the canonical Priority-1 personal-data attributes in text. `[MVP]`
- **FR7:** The system can detect personal data embedded in images via OCR. `[MVP]`
- **FR8:** The system can detect faces/persons in images. `[MVP]`
- **FR9:** The system can detect vehicle licence plates in images. `[MVP]`
- **FR10:** The system can detect signatures in images. `[MVP]`
- **FR11:** The system can detect the German ID card number. `[MVP]`
- **FR11a:** The system can detect the German social security number. `[MVP]`
- **FR11b:** The system can detect the German tax ID. `[MVP]`
- **FR12:** The system can detect IBANs. `[MVP]`
- **FR12a:** The system can detect payment card numbers (PAN). `[MVP]`
- **FR13:** The system can assign each finding a classification from a controlled vocabulary (enum). `[MVP]`
- **FR14:** The system can escalate low-confidence findings to an AI model for a second-opinion verdict. `[MVP]`
- **FR15:** The system can detect personal data in video. `[Growth]`
- **FR16:** The system can detect special-category (Art. 9) data. `[Vision]`

### Scoring & Findings
- **FR17:** The system can assign each finding a legal-risk score. `[MVP]`
- **FR18:** The system can assign each finding a detection-confidence score. `[MVP]`
- **FR19:** The system can record each finding with its location, classification, risk, and confidence — without storing the raw personal-data value. `[MVP]`
- **FR20:** The system can present a masked snippet / location pointer for context. `[MVP]`
- **FR21:** The system can attribute each finding to a responsible data owner. `[MVP]`
- **FR22:** The system can resolve ownership for shared, orphaned, or departed-employee files via a fallback chain. `[Growth]`

### Scan Orchestration
- **FR23:** An administrator can trigger a full scan of a configured source. `[MVP]`
- **FR24:** The system can perform delta scans that re-evaluate only files changed since the last scan. `[MVP]`
- **FR25:** The system can re-evaluate previously-cleared files when detection rules are updated. `[MVP]`
- **FR26:** The system can track and report scan progress and completion. `[MVP]`
- **FR27:** The system can run scans on a recurring schedule. `[Growth]`

### Owner Remediation (User View)
- **FR28:** A data owner can view a list of only their own flagged files. `[MVP]`
- **FR29:** A data owner can see findings ordered by priority, with nothing hidden. `[MVP]`
- **FR30:** A data owner can view each finding in plain language with a consequence explanation. `[MVP]`
- **FR31:** A data owner can confirm a file is needed and record a business justification (guided, not free-text-only). `[MVP]`
- **FR32:** A data owner can delete a flagged file. `[MVP]`
- **FR33:** A data owner can recover a deleted file within a grace period. `[MVP]`
- **FR34:** A data owner can escalate a finding they cannot judge. `[MVP]`
- **FR35:** A data owner can see their own remediation progress. `[MVP]`
- **FR36:** The system can notify owners of new findings via the in-app dashboard and Microsoft Teams. `[MVP]`
- **FR37:** The system can send escalation deadline reminders. `[Growth]`

### Escalation & Ownership
- **FR38:** A line manager (or assigned delegate) can view findings escalated by their reports. `[MVP]`
- **FR39:** A line manager can act on an escalated finding on behalf of the owner, with a logged justification. `[MVP]`
- **FR40:** A line manager can reassign ownership of a file. `[Growth]`

### Admin & Oversight
- **FR41:** An administrator can configure scan sources. `[MVP]`
- **FR42:** A DPO/administrator can view an aggregate dashboard of estate metrics (files scanned, data volume, findings count, scan progress). `[MVP]`
- **FR43:** A DPO can view findings aggregated by classification type. `[MVP]`
- **FR44:** A DPO can view findings trended over time and sliced by org unit. `[Growth]`
- **FR45:** A DPO can export regulator-ready compliance reports. `[Growth]`

### Audit, Compliance & Access
- **FR46:** The system can maintain an immutable audit log linking each finding and action to detector version, model version, and timestamp. `[MVP]`
- **FR47:** The system can produce reproducible results for deterministic detectors. `[MVP]`
- **FR48:** The system can enforce data-retention rules (e.g., 3-year default). `[Growth]`
- **FR49:** Users can authenticate via corporate SSO. `[Growth]` (MVP may mock identity)
- **FR50:** The system can enforce role-based access so owners, line managers, and admins see only what their role permits. `[MVP core; full Growth]`
- **FR51:** The system can guarantee the DPO/admin role cannot view individual personal-data values. `[MVP]`

## Non-Functional Requirements

### Performance (evaluation criteria)
- **NFR1:** Scan throughput is measured as time-to-scan a fixed 1 GB mixed corpus on defined hardware (median of 3 runs); delta scans are materially faster than full scans.
- **NFR2:** User-facing dashboard actions (open queue, act on a finding) complete within ~2 seconds.
- **NFR3:** Tier-2 AI escalation is invoked on only a minority of files (target <10% at scale) to bound cost and latency.

### Resource Efficiency (evaluation criteria)
- **NFR4:** Tier-1 detection runs on commodity CPU (no dedicated GPU required). A resource budget — CPU-core-seconds and peak RAM per GB scanned — is measured on defined reference hardware, with a per-GB ceiling set by the Architect that keeps continuous estate-wide operation viable.
- **NFR5:** Heavy Tier-2 inference is isolated so it never gates the common (Tier-1) path.

### Accuracy & Reliability (evaluation criteria; domain-critical)
- **NFR6:** Entity-level recall on Priority-1 attributes ≥90% (text) / ≥80% (image) at PoC, measured against the labeled eval set; the engine is recall-biased to minimize false negatives.
- **NFR7:** False-positive rate ≤25% at PoC, tolerated because human review filters cheaply.
- **NFR8:** Deterministic detectors produce 100% identical results across repeated runs (reproducibility — a legal property).
- **NFR9:** Top-severity (Art. 9) recall is gated separately at a higher bar than Priority-1 recall and must never fall below the P1 recall floor; the specific numeric threshold is set against the labeled eval set when Art. 9 detection enters scope (Vision).

### Security
- **NFR10:** All data (catalog, findings store, audit log) is encrypted in transit and at rest.
- **NFR11:** The findings store contains no raw PII values (privacy-by-design).
- **NFR12:** In production, no PII is sent to third-party/external AI — inference stays inside the Bosch perimeter.
- **NFR13:** Least-privilege RBAC; the DPO/admin role cannot access individual PII values.
- **NFR14:** The audit log is immutable/tamper-evident and retained beyond a single scan cycle (Art. 5(2) accountability).

### Scalability
- **NFR15:** The architecture scales horizontally toward the full estate (~300k OneDrives + SharePoint + file shares): throughput increases approximately linearly as worker capacity is added (validated by a scale test), with no change to the file-source interface or findings data model required.
- **NFR16:** The delta + catalog approach keeps steady-state cost proportional to change volume, not total estate size.

### Accessibility & Usability
- **NFR17:** The User View is usable by non-expert employees with zero GDPR training — plain language, no jargon.
- **NFR18:** The employee-facing UI meets WCAG 2.1 AA (broad internal audience).
- **NFR19:** 90% of findings are resolvable by an owner in under 60 seconds.

### Integration
- **NFR20:** Integrations with Microsoft Graph (OneDrive/SharePoint) and Entra ID tolerate API rate limits and transient failures (retry/backoff).
- **NFR21:** Notifications are delivered via Microsoft Teams and the in-app dashboard.

### Compliance (cross-cutting)
- **NFR22:** Each governing GDPR article maps to a named, demonstrable control: Art. 5 → retention/minimisation enforcement; Art. 17 → auditable erasure flow; Art. 25 → privacy-by-design findings model + in-perimeter inference; Art. 32 → encryption + RBAC + immutable audit log. Each control is verifiable in the compliance matrix.
