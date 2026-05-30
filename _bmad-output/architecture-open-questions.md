# Architecture Open Questions — Bosch GDPR Data Discovery

Load-bearing items raised in Party Mode (Winston, Architect) + measurement requirements
(Murat, Test Architect). MUST be resolved in the Architecture step before coding.

## Winston's 6 load-bearing walls
1. **Inference / deployment topology — RESOLVED 2026-05-30 (see architecture.md → Deployment & Topology Decision).**
   Production = in-tenant Azure hybrid ("compute goes to the data"): central plane + Tier-2 GPU pool in Bosch
   Azure tenant; on-prem edge workers send findings only; on-prem Tier-2 = ephemeral snippet to central GPU.
   Hackathon build = MVP single-app emulation via seams (FileSource interface, in-proc worker, SQLite catalog,
   hosted LLM on synthetic data). Azure deployment = stretch goal if time allows. Original framing retained below.
   User unsure; do not force. Captured framing as INPUT only (not decided):
   - Key insight: Bosch's own M365/Azure tenant is INSIDE the perimeter — "cloud" is allowed; only
     third-party external AI is forbidden. So in-tenant cloud processing is sovereignty-safe.
   - Candidate principle: "compute goes to the data" (hybrid). M365 sources (OneDrive/SharePoint) →
     central service in Bosch Azure tenant via Graph (no egress). On-prem (file shares/local) → edge
     workers that scan in place, send only FINDINGS (enum+location+scores, never raw PII) to central catalog.
   - Maps to tiers: Tier-1 (YOLO+regex, light/CPU/deterministic) at edge/in-tenant; Tier-2 (LLM/VLM, heavy)
     central GPU pool, low-confidence minority only.
   - Why not pure-desktop (300k unmanageable agents, can't do shared SharePoint) nor pure-central
     (on-prem egress limits, WAN cost). Decides cost-per-TB.
   - ONLY committed decision: MVP/hackathon = single local app (local folder + OneDrive via Graph),
     with a clean file-source interface so it could later run as edge worker or in-tenant service.
2. **Reproducibility as a MECHANISM** — version-lock model weights (immutable per run); version Tier-1 rules
   like software; every finding records which detector/model version produced it; Tier-2 needs weights
   snapshot/hash per job. Define what's stored, format, queryability, retention (Art.5(2) is long-lived).
3. **Tier-1 → Tier-2 escalation threshold** — the single most important parameter. Define a (provisional)
   value, a calibration methodology + dataset, and a feedback loop to tune without full re-scan.
4. **Delta-scan invalidation model** — RESOLVED MECHANISM:
   - Persistent SCAN CATALOG (one row per file): file ID/path, content hash (sha256), size, mtime,
     last-scanned ts, detector RULESET VERSION, findings.
   - Re-scan a file iff: (a) new/not in catalog; (b) content hash changed (mtime+size as cheap pre-filter);
     (c) ruleset/model version newer than catalog's stored version — the KILLER CASE: improved detectors
     force re-eval of previously-"clean" files, else legal gap; (d) previously low-confidence/escalated.
   - Change signal per source: OneDrive/SharePoint = Microsoft Graph /delta query + persisted delta token
     (no full enumeration — the scale answer); NTFS shares = USN Change Journal; generic = mtime+size→hash.
   - Must handle deletions/moves (update/remove catalog rows) to preserve "accounted for" guarantee.
   - MVP: SQLite catalog; demo full→edit+bump rule→delta touches only changed/invalidated files.
   - Pitch point: delta = changed files AND files whose detection rules got smarter (defensible continuous compliance).
5. **Data-ownership resolution policy** — shared drives (many contributors), departed employees, service-account
   owners, duplicate copies. Fallback chain (owner → manager → department DPO). Wrong/void routing = liability.
6. **Video scope** — frame-sampling + transcription + per-frame VLM is unbounded. Cap (max size/duration/fps)
   or defer. (Decision: DEFERRED to Growth in MVP scope.)

## Classification enum — RESOLVED (must stay complete)
COMPLETE enum mapping for ALL attributes (P1 + MVP-P2 + deferred-P2 + P3) is in pii-detection-scope.md:
each row = machine_code + display_label + modality + MVP flag + risk weight + GDPR focus.
HARD RULE: the engine must not emit any classification not in that table; adding a detector requires
adding its enum row first (code + label + risk + GDPR focus). UI renders display_label, never the code.

## Murat's measurement requirements (partly folded into Success Criteria now)
- Build a CLOSED-WORLD LABELED eval set: span/bbox-level ground truth, label provenance + inter-annotator
  agreement (Cohen's κ ≥ 0.8), production-representative distribution. (a-klumpp repo = starting point, not test suite.)
- Entity-level recall (not per-file), stratified by PII category + modality.
- Severity-weighted recall: report per severity tier; pass only if top-severity (Art.9) recall ≥ target.
- Confidence-score CALIBRATION curve (confidence bins vs actual precision); or name the gap explicitly.
- Throughput as time-to-scan a fixed 1GB known-composition corpus on demo HW, median of 3 runs.
- Tier-2 AI = documented non-deterministic; immutable audit log per finding (detector ver, model ver, prompt hash, timestamp).
