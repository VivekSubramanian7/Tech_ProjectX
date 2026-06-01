/** Typed REST API client — base URL configurable via VITE_API_BASE_URL. */

const BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";

const OWNER_USER_KEY = "gdpr_owner_id";
export const DEMO_OWNER_ID = "user-alpha";

export const DEMO_OWNERS = [
  { id: "user-alpha", label: "Team Alpha", hint: "team-alpha/ files" },
  { id: "user-beta", label: "Team Beta", hint: "team-beta/ files" },
] as const;

export type DemoOwnerId = (typeof DEMO_OWNERS)[number]["id"];

function ownerUserId(): string {
  return localStorage.getItem(OWNER_USER_KEY) ?? DEMO_OWNER_ID;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

function ownerRequest<T>(path: string, init?: RequestInit): Promise<T> {
  return request<T>(path, {
    ...init,
    headers: {
      "X-Acting-User": ownerUserId(),
      ...init?.headers,
    },
  });
}

// ── Types ──────────────────────────────────────────────────────────────────

export interface ScanStatus {
  scan_id: string;
  status: "scanning" | "complete" | "error" | "queued";
  files_total: number;
  files_scanned: number;
  findings_count: number;
  mode: string;
  current_file?: string | null;
  phase?: string | null;
  started_ts?: string;
  completed_ts?: string | null;
  tier2_applied?: number;
  total_bytes?: number;
  duration_ms?: number | null;
  type_breakdown?: Record<string, { files: number; bytes: number }> | null;
}

export interface ClassificationBucket {
  code: string;
  display_label: string;
  count: number;
  risk_weight: "Critical" | "High" | "Medium" | "Low";
}

export interface Aggregates {
  files_scanned: number;
  total_size_bytes: number;
  open_findings: number;
  total_findings: number;
  by_classification: ClassificationBucket[];
  tier2_needed: number;
  tier2_verified: number;
  assurance_pct: number;
}

export interface Capabilities {
  graph_access: boolean;
  models_ready?: boolean;
}

export interface OwnerFinding {
  id: number;
  file_id: string;
  file_path: string;
  classification_code: string;
  display_label: string;
  risk_weight: "Critical" | "High" | "Medium" | "Low";
  consequence_hint: string;
  masked_snippet: string;
  confidence_label: "Likely" | "Not sure";
  location: Record<string, unknown>;
  resolution_status: string;
}

export interface OwnerFindingsResponse {
  data: OwnerFinding[];
  meta: { owner_user_id: string; open_count: number };
}

export interface FileContentPreview {
  file_id: string;
  file_path: string;
  renderable: boolean;
  media_type: string | null;
  content: string | null;
  unsupported_reason: string | null;
}

// ── Endpoints ──────────────────────────────────────────────────────────────

export const api = {
  health: () => request<{ status: string }>("/health"),

  capabilities: () => request<Capabilities>("/capabilities"),

  scans: {
    list: () => request<{ data: ScanStatus[] }>("/scans"),
    get: (id: string) => request<{ data: ScanStatus }>(`/scans/${id}`),
    create: (body: { path?: string; mode?: "full" | "delta"; use_config?: boolean }) =>
      request<{ data: ScanStatus; meta: { scan_id: string; mode: string } }>("/scans", {
        method: "POST",
        body: JSON.stringify(body),
      }),
  },

  aggregates: () => request<{ data: Aggregates }>("/aggregates"),

  admin: {
    reset: () =>
      request<{ data: { reset: boolean }; meta: { message: string } }>("/aggregates/reset", {
        method: "POST",
      }),
  },

  owner: {
    findings: () => ownerRequest<OwnerFindingsResponse>("/me/findings"),
    fileContent: (fileId: string) =>
      ownerRequest<{ data: FileContentPreview }>(`/me/files/${encodeURIComponent(fileId)}/content`),
    keep: (id: number, reason: string) =>
      ownerRequest<{ data: OwnerFinding }>(`/findings/${id}/keep`, {
        method: "POST",
        body: JSON.stringify({ reason }),
      }),
    delete: (id: number) =>
      ownerRequest<{ data: OwnerFinding }>(`/findings/${id}/delete`, { method: "POST" }),
    restore: (id: number) =>
      ownerRequest<{ data: OwnerFinding }>(`/findings/${id}/restore`, { method: "POST" }),
    escalate: (id: number, reason: string) =>
      ownerRequest<{ data: OwnerFinding }>(`/findings/${id}/escalate`, {
        method: "POST",
        body: JSON.stringify({ reason }),
      }),
    falsePositive: (id: number) =>
      ownerRequest<{ data: OwnerFinding }>(`/findings/${id}/false-positive`, {
        method: "POST",
      }),
  },
};
