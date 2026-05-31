---
stepsCompleted: [1, 2, 3, 4]
completedDate: '2026-05-31'
status: complete
inputDocuments:
  - '_bmad-output/prd.md'
  - '_bmad-output/architecture.md'
  - '_bmad-output/ux-design-specification.md'
  - '_bmad-output/pii-detection-scope.md'
scope: 'UI/FRONTEND domain only — Owner View + Admin View (MVP). Complements _bmad-output/epics.md (scan engine, FR1-FR27). Escalation/line-manager UI (FR38-FR40) deferred.'
storyStyle: 'Self-contained: each story embeds context (target files, component specs, API/findings contracts, UX refs, ACs) for an independent subagent to implement.'
---

# Bosch GDPR Data Discovery (UI: Owner + Admin) - Epic Breakdown

## Overview

This document decomposes the **UI/frontend** slice (Owner View + Admin View) into
implementable, self-contained stories. It complements the scan-engine epics in
`_bmad-output/epics.md` (FR1-FR27). Sources: PRD (UI FRs + usability NFRs), Architecture
(React+Vite+TS SPA, role-gated routes, findings-store contract), UX Design Specification
(components, tokens, flows, patterns), pii-detection-scope.md (classification enum).

## Requirements Inventory

### Functional Requirements (UI domain)

**Owner Remediation (User View)**
- FR28: A data owner can view a list of only their own flagged files. `[MVP]`
- FR29: A data owner can see findings ordered by priority, with nothing hidden. `[MVP]`
- FR30: A data owner can view each finding in plain language with a consequence explanation. `[MVP]`
- FR31: A data owner can confirm a file is needed and record a business justification (guided, not free-text-only). `[MVP]`
- FR32: A data owner can delete a flagged file. `[MVP]`
- FR33: A data owner can recover a deleted file within a grace period. `[MVP]`
- FR34: A data owner can escalate a finding they cannot judge. `[MVP]`
- FR35: A data owner can see their own remediation progress. `[MVP]`
- FR36: The system can notify owners of new findings via the in-app dashboard and Microsoft Teams. `[MVP]`
- FR-UI1 (new, from product direction): A data owner can flag a finding as a **false positive** ("not personal data"), which is acknowledged and fed back to improve engine precision. `[MVP]`

**Findings Presentation (consumed by UI)**
- FR19: Findings carry location, classification, risk, and confidence — never the raw PII value. `[MVP]`
- FR20: The system presents a masked snippet / location pointer for context. `[MVP]`

**Admin & Oversight**
- FR23: An administrator can trigger a full scan of a configured source. `[MVP]` (UI trigger)
- FR26: The system tracks and reports scan progress and completion. `[MVP]` (UI surfacing)
- FR41: An administrator can configure scan sources (local folder; OneDrive if backend Graph access). `[MVP]`
- FR42: A DPO/administrator can view an aggregate dashboard (files scanned, data volume, findings count, scan progress). `[MVP]`
- FR43: A DPO can view findings aggregated by classification type. `[MVP]`

**Access Control (UI enforcement)**
- FR50: The system enforces role-based access so owners, line managers, and admins see only what their role permits. `[MVP core]`
- FR51: The DPO/admin role cannot view individual personal-data values. `[MVP]`

**Deferred (out of this UI MVP slice)**
- FR37 escalation reminders `[Growth]`; FR38-FR40 line-manager escalation UI / act-on-behalf / reassign `[deferred]`;
  FR44 trends + org-unit slicing `[Growth]`; FR45 regulator export `[Growth]`; FR49 SSO `[Growth, MVP may mock]`.

### NonFunctional Requirements (UI-relevant)

- NFR2: User-facing dashboard actions (open queue, act on a finding) complete within ~2 seconds.
- NFR13: Least-privilege RBAC; the DPO/admin role cannot access individual PII values.
- NFR17: The User View is usable by non-expert employees with zero GDPR training — plain language, no jargon.
- NFR18: The employee-facing UI meets WCAG 2.1 AA.
- NFR19: 90% of findings are resolvable by an owner in under 60 seconds.
- NFR21: Notifications are delivered via Microsoft Teams and the in-app dashboard.

### Additional Requirements (Architecture)

- **Starter template:** `web/` is a Vite scaffold; Epic 1 Story 1 = scaffold React+TS + Tailwind + shadcn/ui (per architecture "create-vite react-ts").
- **Three role-gated route trees** (Owner / Line-Manager / DPO) share **one component library** (`web/src/components/`).
- **Findings-store contract:** UI reads enum `code` + `display_label` + location + risk + confidence + masked snippet; **never** a raw PII value. Classification `display_label` (never the machine code) is what the UI shows.
- **API:** FastAPI backend; SPA consumes REST endpoints for queue, actions, scan control, and aggregates.
- **File identity:** `file_id = sha256(source_type:scope_id:native_id)` used as the stable finding/file key.

### UX Design Requirements

- UX-DR1: **Design token layer** (CSS variables) — neutral-calm palette; risk encoded by queue order + quiet left edge, **never alarm-red**; confidence as worded chip.
- UX-DR2: **Tailwind + shadcn/ui (Radix)** setup; Recharts for charts; one shared theme across Owner + Admin.
- UX-DR3: **FindingCard** component (classification display_label, consequence hint, confidence chip, masked snippet, risk edge).
- UX-DR4: **ActionBar** — Keep / Delete / Escalate / "Not personal data" with `K/D/E/F` keyboard shortcuts.
- UX-DR5: **ConfidenceChip** (worded "Likely"/"Not sure", never %).
- UX-DR6: **MaskedSnippet** (mono masked value + "Open document").
- UX-DR7: **ReasonPicker** — guided dropdown of retention reasons + optional "Add detail".
- UX-DR8: **DocumentViewer** — inline file with finding highlighted; owner-only; audited; unsupported-type → location-pointer fallback.
- UX-DR9: **QueueProgress + AllClear/streak** — progress framing ("3 of 47") + restrained queue-to-zero celebration (gamification).
- UX-DR10: **FocusView + ListView toggle** — single-card focus (default) and Compact-Triage dense list over the same atoms.
- UX-DR11: **Act-then-undo Toast (Sonner)** — soft-delete with "Undo"; no blocking confirm modals.
- UX-DR12: **ScanLauncher + SourcePicker** — folder picker + OneDrive connect (visible-disabled-with-reason if no Graph access).
- UX-DR13: **ScanProgress** — live files/size/% during a scan.
- UX-DR14: **KpiTile** — total processed size, files scanned, findings count.
- UX-DR15: **ThroughputChart** — files-processed-over-time **area chart** (Recharts), x-axis = time.
- UX-DR16: **ClassificationBreakdown** — findings aggregated by classification enum.
- UX-DR17: **Accessibility** — WCAG 2.1 AA: contrast, visible focus rings, full keyboard nav, `aria-live` progress, `prefers-reduced-motion`.
- UX-DR18: **Plain-language pass** — every UI string free of GDPR jargon (no article numbers, no "data subject").
- UX-DR19: **Empty/loading states** — skeleton cards/tiles; celebratory empty ("All clear 🎉" / "No scans yet").
- UX-DR20: **False-positive feedback loop** — flag → acknowledgment toast → recorded for engine precision tuning.

### FR Coverage Map

- FR19: Epic 1 — findings shown with classification + location, no raw value
- FR20: Epic 1 — masked snippet / location pointer
- FR28: Epic 1 — owner sees only their own flagged files
- FR29: Epic 1 — findings ordered by priority, nothing hidden
- FR30: Epic 1 — plain-language finding with consequence hint
- FR31: Epic 1 — keep + guided reason
- FR32: Epic 1 — delete
- FR33: Epic 1 — recover within grace period (undo / soft-delete)
- FR34: Epic 1 — escalate
- FR-UI1: Epic 1 — false-positive flag + acknowledgment
- FR23: Epic 1 — admin triggers a full scan (data producer)
- FR26: Epic 1 — scan progress + completion surfaced
- FR41: Epic 1 — configure sources (folder; OneDrive conditional)
- FR42: Epic 1 — aggregate KPI dashboard
- FR43: Epic 1 — findings aggregated by classification
- FR50: Epic 1 (admin scope) + Epic 2 (owner scope)
- FR51: Epic 1 + Epic 2 — admin never sees individual PII
- FR28: Epic 2 — owner sees only their own flagged files
- FR29: Epic 2 — findings ordered by priority, nothing hidden
- FR30: Epic 2 — plain-language finding with consequence hint
- FR31: Epic 2 — keep + guided reason
- FR32: Epic 2 — delete
- FR33: Epic 2 — recover within grace period (undo / soft-delete)
- FR34: Epic 2 — escalate
- FR-UI1: Epic 2 — false-positive flag + acknowledgment
- FR35: Epic 2 (progress) + Epic 3 (gamified throughput)
- FR36: Epic 2 — in-app + Teams notification entry point

*Cross-cutting NFRs:* NFR13 → Epic 1 (admin RBAC); NFR2 / NFR17 / NFR18 / NFR19 → Epic 2 + Epic 3;
NFR21 → Epic 2. *Deferred:* FR37, FR38–FR40 (line-manager), FR44, FR45, FR49.

**Build order = epic order** (Admin first so a real scan produces the findings the Owner epic
consumes — no hard fixture dependency; the existing engine scans `data/corpus/` for real data).

## Epic List

### Epic 1: Admin — Scan a folder & see the picture (data producer; owns the shared foundation)
A DPO/admin triggers a scan on a chosen folder (or OneDrive, if backend has Graph access),
watches live progress, and reads the aggregate picture — total processed size, files, findings
count, a files-over-time area chart, and findings by classification — never seeing individual PII.
Built first so it populates the catalog with real findings for the Owner epic. Includes the app
scaffold, design tokens, shared UI kit, API client, and role-gated shell.
**FRs covered:** FR23, FR26, FR41, FR42, FR43, FR50 (admin), FR51 · UX-DR 1, 2, 12–17, 19

### Epic 2: Owner — Resolve my flagged files (core remediation loop)
A data owner opens a calm, prioritized queue of only their own findings and resolves each in
plain language — Keep (guided reason) / Delete (reversible soft-delete) / Escalate / Not
personal data — viewing the document in context when needed, until "all clear." Consumes the
real findings Epic 1 produced (a tiny fixture set is kept only for unit tests). This is the
product's core value — owner-decides.
**FRs covered:** FR28, FR29, FR30, FR31, FR32, FR33, FR34, FR-UI1, FR35, FR36, FR19, FR20, FR50 (owner), FR51 · UX-DR 3–8, 11, 17, 18

### Epic 3: Owner — Make it satisfying (gamification + throughput)
Clearing the queue feels good and power users move fast: a restrained queue-to-zero
celebration + streak, a Compact-Triage list-view toggle for many findings, and polished
empty/loading states. Standalone delight layer on top of Epic 2; first de-scope if time runs short.
**FRs covered:** FR35 (reinforced) · UX-DR 9, 10, 19

<!-- ============================ EPIC DETAILS ============================ -->

## Epic 1: Admin — Scan a folder & see the picture

Build the data-producing admin surface on top of a shared foundation. By the end, an admin can
scan `data/corpus/` (or any folder) and the catalog holds real, contract-conformant findings
that Epic 2 consumes — and the admin sees the estate picture without ever touching a PII value.

### Story 1.1: Shared foundation — scaffold, tokens, UI kit, API client, role-gated shell

As an engineering team,
I want the web app scaffolded with the design system and a role-gated shell,
So that both the Admin and Owner surfaces build on one consistent, accessible foundation.

**Acceptance Criteria:**

**Given** the `web/` Vite+TS scaffold,
**When** the foundation is set up,
**Then** React + Vite + TypeScript builds and runs with Tailwind + shadcn/ui configured and the neutral-calm design tokens (CSS variables) from the UX spec applied,
**And** no Bosch-red / alarm-red is used as a primary or risk signal.

**Given** the app shell,
**When** a user navigates to a role-gated route (`/admin`, `/owner`),
**Then** the correct surface renders and an unauthorized role is denied (RBAC stub).

**Given** a typed REST API client (`web/src/lib/api.ts`, configurable base URL),
**When** any view needs data,
**Then** it calls the client with consistent loading and error handling.

**Given** WCAG 2.1 AA,
**Then** global styles include visible focus rings, keyboard operability, and `prefers-reduced-motion` support.

*Context: `web/src/main.tsx`, `web/src/app/router`, `web/src/components/` (shared atoms), `web/src/lib/api.ts`, `tailwind.config`, `tokens.css`. Stack per architecture: React+Vite+TS, Tailwind, shadcn/ui, Recharts.*

### Story 1.2: Trigger a scan on a folder source (findings land in the catalog)

As a DPO/admin,
I want to start a scan on a chosen local folder,
So that the system discovers personal data and findings populate the catalog.

**Acceptance Criteria:**

**Given** the Admin pane,
**When** the admin enters/picks a folder path and clicks "Start scan",
**Then** the SPA calls the scan API (e.g. `POST /scans {source:"local", path}`) and a scan is created and runs the existing engine pipeline.

**Given** a completed scan,
**Then** findings are persisted conforming to the findings contract (classification code + location + risk + confidence + masked snippet, **no raw PII value**).

**Given** `data/corpus/` as the folder,
**When** scanned,
**Then** real findings are queryable via the API — this is the data source Epic 2 consumes.

**Given** an invalid / empty / unreadable folder,
**Then** a clear inline error is shown and no scan is created.

*Context: `ScanLauncher`, `SourcePicker` components; `engine/app/api/scans.py` (POST); reuses the existing scan orchestrator.*

### Story 1.3: OneDrive source (conditional / disabled-with-reason)

As an admin,
I want to connect OneDrive as a scan source when the backend supports it,
So that I can scan cloud drives — and understand why if I cannot.

**Acceptance Criteria:**

**Given** the backend reports Graph access available (`GET /capabilities`),
**When** the admin opens source options,
**Then** "OneDrive" is selectable and connecting lets them pick a drive.

**Given** the backend reports no Graph access,
**Then** the OneDrive option is **visible but disabled with a tooltip** explaining why (never hidden).

**Given** OneDrive is selected,
**When** a scan is triggered,
**Then** it behaves like Story 1.2 with `source:"onedrive"`.

*Context: `SourcePicker` conditional state; capability flag from API.*

### Story 1.4: Live scan progress

As an admin,
I want to watch a scan progress in real time,
So that I know it is working and when it is done.

**Acceptance Criteria:**

**Given** a running scan,
**When** the admin views it,
**Then** files processed, size processed, and % complete update live (poll or stream) with `aria-live` announcements.

**Given** completion,
**Then** a "done" state shows totals and links to the dashboard.

**Given** an error mid-scan,
**Then** a retry affordance is shown and visible progress is not lost.

*Context: `ScanProgress` component; `GET /scans/{id}` status.*

### Story 1.5: KPI tiles + admin RBAC (never sees PII)

As a DPO,
I want headline metrics,
So that I can see the estate picture without touching any file.

**Acceptance Criteria:**

**Given** completed scan data,
**When** the dashboard loads,
**Then** `KpiTile`s show total processed size, files scanned, and findings count from an aggregate endpoint.

**Given** the admin role,
**Then** no admin view exposes a raw PII value or a person-linked snippet — only counts/sizes (FR51 / NFR13); an API request for per-file PII is denied for this role.

**Given** NFR2,
**Then** tiles render within ~2s on the demo dataset.

*Context: `KpiTile`; `GET /aggregates`; server-side RBAC guard.*

### Story 1.6: Findings by classification

As a DPO,
I want findings broken down by classification type,
So that I can see which kinds of personal data dominate.

**Acceptance Criteria:**

**Given** aggregate data,
**When** the dashboard loads,
**Then** `ClassificationBreakdown` shows counts per classification using the human **display_label** (never the machine enum code), ordered by count.

**Given** the enum,
**Then** zero-count classifications are handled consistently (omitted or shown as zero).

*Context: `ClassificationBreakdown`; aggregates keyed by enum; `pii-detection-scope.md` display labels.*

### Story 1.7: Files-processed-over-time area chart

As a DPO,
I want a chart of files processed over time,
So that I can see throughput.

**Acceptance Criteria:**

**Given** scan time-series data,
**When** the dashboard loads,
**Then** a Recharts **area chart** renders with x-axis = time and y = files processed.

**Given** accessibility,
**Then** a table fallback or `aria` description is available for screen readers.

**Given** no scans yet,
**Then** an empty state ("No scans yet — start one") shows instead of a broken chart.

*Context: `ThroughputChart` (Recharts); `GET /scans` time-series.*

## Epic 2: Owner — Resolve my flagged files

The product's core value. Consumes the real findings produced by Epic 1 (a small fixture set is
used only for unit tests). By the end, a data owner clears their queue in plain language, safely
and fast.

### Story 2.1: My findings queue (only mine, ordered, nothing hidden)

As a data owner,
I want a prioritized queue of only my own flagged files,
So that I can work through exactly what needs me.

**Acceptance Criteria:**

**Given** findings attributed to me,
**When** I open my queue,
**Then** I see only my own findings, ordered by risk **silently** (no risk number shown), with nothing suppressed (FR28, FR29).

**Given** another owner's findings,
**Then** they never appear in my queue (RBAC, FR50).

**Given** no findings,
**Then** a celebratory empty state shows ("All clear 🎉").

*Context: `web/src/owner/Queue.tsx`; `GET /me/findings`; renders from real Epic-1 catalog data (+ fixtures in unit tests).*

### Story 2.2: Finding card in plain language (masked, no raw PII)

As a data owner,
I want each finding explained plainly,
So that I understand what it is and why it matters without GDPR knowledge.

**Acceptance Criteria:**

**Given** a finding,
**When** it renders,
**Then** the `FindingCard` shows the classification **display_label**, a plain consequence hint, a worded `ConfidenceChip` ("Likely"/"Not sure", never %), and a `MaskedSnippet` (e.g. `•••••4521`) — never a raw PII value (FR19, FR20, FR30; NFR17).

**Given** risk,
**Then** it is conveyed only by queue order + a quiet left edge — never a number or alarm color.

*Context: `FindingCard`, `ConfidenceChip`, `MaskedSnippet`.*

### Story 2.3: Keep with a guided reason

As a data owner,
I want to confirm I still need a file and record why with minimal effort,
So that keeping is justified but fast.

**Acceptance Criteria:**

**Given** a finding,
**When** I click Keep,
**Then** a `ReasonPicker` offers common reasons (dropdown) with an optional "Add detail"; selecting one records the justification and resolves the finding (FR31).

**Given** the nudge design,
**Then** Keep takes slightly more effort than Delete but still completes in a few seconds, and the choice is changeable later.

*Context: `ReasonPicker`; `POST /findings/{id}/keep {reason}`.*

### Story 2.4: Delete with reversible soft-delete + undo

As a data owner,
I want deleting to feel safe,
So that I am not afraid to remove files.

**Acceptance Criteria:**

**Given** a finding,
**When** I click Delete,
**Then** it is optimistically removed and a toast shows "Scheduled for deletion in 14 days — Undo" (FR32, FR33).

**Given** the toast / grace period,
**When** I click Undo,
**Then** the file/finding is restored.

**Given** the calm principle,
**Then** deletion never blocks behind a confirm modal.

*Context: `ActionBar` + Sonner toast; `POST /findings/{id}/delete` (soft) and `.../restore`.*

### Story 2.5: Escalate a finding I cannot judge

As a data owner,
I want to hand off findings I cannot decide,
So that I do not default to hoarding.

**Acceptance Criteria:**

**Given** a finding,
**When** I click "I'm not sure",
**Then** I pick a reason and it leaves my queue, routed to my line manager/delegate (FR34), and stays accounted for (not deleted).

**Given** escalation,
**Then** my queue advances and progress updates.

*Context: escalate action; `POST /findings/{id}/escalate {reason}`. Manager inbox UI is deferred.*

### Story 2.6: Flag a false positive

As a data owner,
I want to say "this isn't personal data",
So that wrong detections stop bothering me and the engine improves.

**Acceptance Criteria:**

**Given** a finding,
**When** I click "Not personal data",
**Then** the finding is dismissed and an acknowledgment toast shows ("Thanks — this sharpens detection") (FR-UI1).

**Given** the flag,
**Then** a feedback signal is recorded via the API for engine precision tuning (no raw PII in the signal).

*Context: `POST /findings/{id}/false-positive`.*

### Story 2.7: View the document in context

As a data owner,
I want to open the actual file with the finding highlighted,
So that I can decide with full context.

**Acceptance Criteria:**

**Given** a finding,
**When** I click "Open document",
**Then** the `DocumentViewer` loads the source file inline with the finding location highlighted; it is owner-only and the view is audited.

**Given** an unsupported/unrenderable file,
**Then** a graceful fallback shows the location pointer instead.

**Given** RBAC,
**Then** only the owner of the file can open it.

*Context: `DocumentViewer`; `GET /me/files/{id}/content` (owner-only, audited).*

### Story 2.8: Progress + notifications

As a data owner,
I want to see my progress and be nudged,
So that resolving feels manageable.

**Acceptance Criteria:**

**Given** a queue,
**Then** progress shows "x of y" (FR35) and updates as I act.

**Given** new findings,
**When** I am notified,
**Then** an in-app indicator and a Microsoft Teams message link me to my queue (FR36, NFR21); the Teams link opens the desktop web app.

*Context: `QueueProgress`; notification entry (a mocked Teams send is acceptable for MVP).*

## Epic 3: Owner — Make it satisfying

Optional delight layer on top of Epic 2 — the first thing to de-scope if time runs short.

### Story 3.1: Queue-to-zero celebration + streak

As a data owner,
I want a satisfying moment when I clear my queue,
So that the chore feels rewarding.

**Acceptance Criteria:**

**Given** I resolve my last finding,
**Then** a restrained "All clear ✓" celebration shows and a streak increments (UX-DR9),
**And** it honors `prefers-reduced-motion` (degrades to a static state).

**Given** the gamification ethic,
**Then** nothing rewards deletion specifically — only resolution/accountability.

*Context: `AllClear`, `StreakBadge`.*

### Story 3.2: Compact-Triage list view toggle

As a power user with many findings,
I want a dense list view,
So that I can clear them fast.

**Acceptance Criteria:**

**Given** the queue,
**When** I toggle Focus ↔ List,
**Then** the same findings render as compact rows with inline actions, reusing the same atoms and logic (UX-DR10).

**Given** either view,
**Then** keep/delete/escalate/false-positive behave identically and risk-by-order is preserved.

*Context: view toggle (Tabs/Switch); `ListView` over the same `FindingCard` atoms.*

### Story 3.3: Polished empty & loading states

As any user,
I want clear empty and loading feedback,
So that the app never feels broken.

**Acceptance Criteria:**

**Given** loading,
**Then** skeleton cards/tiles show (no spinners on blank) (UX-DR19).

**Given** empty states,
**Then** celebratory owner ("All clear 🎉") and admin ("No scans yet — start one") messages show.

*Context: skeleton + empty-state components shared across owner and admin.*
