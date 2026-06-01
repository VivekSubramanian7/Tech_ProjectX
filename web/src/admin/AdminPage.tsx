import { useState, useEffect, useCallback, useRef } from "react";
import {
  Files,
  ScanSearch,
  AlertTriangle,
  Database,
  LogOut,
  RefreshCw,
  Trash2,
  ShieldQuestion,
  ShieldCheck,
  Cpu,
  Sparkles,
  Activity,
  XCircle,
  CheckCircle2,
  PlayCircle,
} from "lucide-react";
import { toast } from "sonner";
import { api, type Aggregates, type ScanStatus, type Tier2JobStatus } from "@/lib/api";
import { useRole } from "@/lib/rbac";
import { formatBytes } from "@/lib/utils";
import { KpiTile } from "@/components/KpiTile";
import ScanLauncher from "./ScanLauncher";
import ClassificationBreakdown from "./ClassificationBreakdown";
import ThroughputChart from "./ThroughputChart";
import ScanPerformance from "./ScanPerformance";

export default function AdminPage() {
  const { setRole } = useRole();
  const [aggregates, setAggregates] = useState<Aggregates | null>(null);
  const [scans, setScans] = useState<ScanStatus[]>([]);
  const [aggLoading, setAggLoading] = useState(true);
  const [scansLoading, setScansLoading] = useState(true);
  const [aggError, setAggError] = useState<string | null>(null);
  const [resetting, setResetting] = useState(false);
  const [tier2Job, setTier2Job] = useState<Tier2JobStatus | null>(null);
  const [tier2Running, setTier2Running] = useState(false);
  const tier2PollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchAggregates = useCallback(() => {
    setAggLoading(true);
    api
      .aggregates()
      .then((res) => {
        setAggregates(res.data);
        setAggError(null);
      })
      .catch((e) => setAggError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setAggLoading(false));
  }, []);

  const fetchScans = useCallback(() => {
    setScansLoading(true);
    api.scans
      .list()
      .then((res) => setScans(res.data))
      .catch(() => null)
      .finally(() => setScansLoading(false));
  }, []);

  useEffect(() => {
    fetchAggregates();
    fetchScans();
  }, [fetchAggregates, fetchScans]);

  function handleScanComplete() {
    fetchAggregates();
    fetchScans();
  }

  async function handleReset() {
    const confirmed = window.confirm(
      "Reset all scan data? This clears scans, findings, audit history, and KPIs. This cannot be undone.",
    );
    if (!confirmed) return;

    setResetting(true);
    try {
      await api.admin.reset();
      toast.success("Scan catalog reset");
      fetchAggregates();
      fetchScans();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Reset failed");
    } finally {
      setResetting(false);
    }
  }

  async function handleRunTier2() {
    setTier2Running(true);
    try {
      const res = await api.tier2.run();
      setTier2Job(res.data);
      // Poll until complete
      tier2PollRef.current = setInterval(async () => {
        try {
          const status = await api.tier2.status();
          setTier2Job(status.data);
          if (status.data.status !== "running") {
            if (tier2PollRef.current) clearInterval(tier2PollRef.current);
            setTier2Running(false);
            if (status.data.status === "complete") {
              toast.success(
                `Tier-2 complete — ${status.data.confirmed} confirmed, ${status.data.rejected} rejected`,
              );
            } else {
              toast.error("Tier-2 pass encountered an error");
            }
            fetchAggregates();
          }
        } catch {
          if (tier2PollRef.current) clearInterval(tier2PollRef.current);
          setTier2Running(false);
        }
      }, 1500);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to start Tier-2 pass");
      setTier2Running(false);
    }
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Nav */}
      <header className="sticky top-0 z-10 border-b border-border bg-card/80 backdrop-blur-sm">
        <div className="max-w-5xl mx-auto px-4 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ScanSearch className="w-5 h-5 text-primary" />
            <span className="font-semibold text-sm">GDPR Discovery</span>
            <span className="text-xs text-muted-foreground bg-muted rounded px-1.5 py-0.5 ml-1">Admin</span>
          </div>
          <button
            onClick={() => setRole(null)}
            className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            <LogOut className="w-3.5 h-3.5" /> Switch role
          </button>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-8 space-y-8">
        {/* Scan trigger */}
        <section aria-labelledby="scan-section-heading">
          <h1 id="scan-section-heading" className="text-lg font-semibold mb-4">
            Run a scan
          </h1>
          <ScanLauncher onScanComplete={handleScanComplete} />
        </section>

        {/* KPI tiles */}
        <section aria-labelledby="kpi-section" id="kpi-section">
          <div className="flex items-center justify-between mb-4">
            <h2 id="kpi-section" className="text-lg font-semibold">
              Estate overview
            </h2>
            <div className="flex items-center gap-3">
            <button
              onClick={() => { fetchAggregates(); fetchScans(); }}
              className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
              aria-label="Refresh dashboard"
            >
              <RefreshCw className="w-3.5 h-3.5" /> Refresh
            </button>
            <button
              onClick={handleReset}
              disabled={resetting || aggLoading}
              className="inline-flex items-center gap-1 text-xs text-destructive hover:text-destructive/80 disabled:opacity-50 transition-colors"
              aria-label="Reset scan catalog"
            >
              <Trash2 className="w-3.5 h-3.5" /> {resetting ? "Resetting…" : "Reset data"}
            </button>
            </div>
          </div>

          {aggError && (
            <div className="flex items-center gap-2 text-sm text-destructive bg-destructive/5 rounded-md px-3 py-2 mb-4">
              <AlertTriangle className="w-4 h-4" /> {aggError}
              <span className="text-xs text-muted-foreground ml-1">
                (start the backend: <code>uvicorn app.main:app --reload</code>)
              </span>
            </div>
          )}

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <KpiTile
              label="Files in catalog"
              value={aggregates?.files_scanned ?? 0}
              icon={<Files className="w-4 h-4" />}
              loading={aggLoading}
            />
            <KpiTile
              label="Data processed"
              value={aggregates ? formatBytes(aggregates.total_size_bytes) : "—"}
              icon={<Database className="w-4 h-4" />}
              loading={aggLoading}
            />
            <KpiTile
              label="Open findings"
              value={aggregates?.open_findings ?? 0}
              icon={<AlertTriangle className="w-4 h-4" />}
              loading={aggLoading}
            />
            <KpiTile
              label="Need Tier-2 check"
              value={aggregates?.tier2_needed ?? 0}
              sub="low-confidence → LLM confirm"
              icon={<ShieldQuestion className="w-4 h-4" />}
              loading={aggLoading}
            />
          </div>
        </section>

        {/* Owner decisions */}
        <section aria-labelledby="decisions-section">
          <h2 id="decisions-section" className="text-lg font-semibold mb-4">
            Owner decisions
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <KpiTile
              label="Retained"
              value={aggregates?.retained ?? 0}
              sub="owner kept the file"
              icon={<ShieldCheck className="w-4 h-4" />}
              loading={aggLoading}
            />
            <KpiTile
              label="Deleted"
              value={aggregates?.deleted ?? 0}
              sub="pending soft-delete"
              icon={<Trash2 className="w-4 h-4" />}
              loading={aggLoading}
            />
            <KpiTile
              label="Not sure"
              value={aggregates?.escalated ?? 0}
              sub="escalated to manager"
              icon={<ShieldQuestion className="w-4 h-4" />}
              loading={aggLoading}
            />
            <KpiTile
              label="Not GDPR-relevant"
              value={aggregates?.not_relevant ?? 0}
              sub="flagged false-positive"
              icon={<XCircle className="w-4 h-4" />}
              loading={aggLoading}
            />
          </div>
        </section>

        {/* Tiered detection assurance — Tier 1 (deterministic) → Tier 2 (LLM) */}
        <section
          aria-labelledby="assurance-heading"
          className="rounded-lg border border-border bg-card p-5"
        >
          <h2 id="assurance-heading" className="font-semibold mb-4 flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-muted-foreground" />
            Detection assurance (tiered)
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Tier 1 first — deterministic, no LLM */}
            <div className="rounded-md border border-border bg-background p-4">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Tier 1 · Deterministic (no LLM)
                </span>
                <Cpu className="w-4 h-4 text-muted-foreground" />
              </div>
              <div className="flex items-baseline gap-2">
                <span className="text-3xl font-semibold tabular-nums">
                  {aggregates && aggregates.open_findings > 0
                    ? `${aggregates.assurance_pct}%`
                    : "0%"}
                </span>
                <span className="text-xs text-muted-foreground">assured</span>
              </div>
              <p className="text-xs text-muted-foreground mt-1.5">
                {aggregates ? aggregates.open_findings - aggregates.tier2_needed : 0} of{" "}
                {aggregates?.open_findings ?? 0} detections are high-confidence from regex /
                checksum / NER / ONNX — no LLM needed.
              </p>
            </div>

            {/* Tier 2 second — LLM confirmation */}
            <div className="rounded-md border border-border bg-background p-4">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Tier 2 · LLM confirmation
                </span>
                <Sparkles className="w-4 h-4 text-muted-foreground" />
              </div>
              <div className="flex items-baseline gap-2">
                <span className="text-3xl font-semibold tabular-nums">
                  {aggregates && aggregates.open_findings > 0
                    ? `${(100 - aggregates.assurance_pct).toFixed(1)}%`
                    : "0%"}
                </span>
                <span className="text-xs text-muted-foreground">need confirmation</span>
              </div>
              <p className="text-xs text-muted-foreground mt-1.5">
                <span className="font-medium text-foreground">{aggregates?.tier2_needed ?? 0}</span> of{" "}
                {aggregates?.open_findings ?? 0} detections fall below the risk-tiered confidence
                threshold — pass to the Tier-2 LLM <span className="font-medium">just for confirmation</span>.
                {aggregates && aggregates.tier2_verified > 0 && (
                  <> {aggregates.tier2_verified} already verified.</>
                )}
              </p>

              {/* Explicit Tier-2 trigger */}
              <div className="mt-3 pt-3 border-t border-border">
                <button
                  onClick={handleRunTier2}
                  disabled={tier2Running || (aggregates?.tier2_needed ?? 0) === 0}
                  className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {tier2Running ? (
                    <>
                      <Sparkles className="w-3.5 h-3.5 animate-pulse" />
                      Running… {tier2Job ? `${tier2Job.processed} processed` : ""}
                    </>
                  ) : (
                    <>
                      <PlayCircle className="w-3.5 h-3.5" />
                      Run Tier-2 confirmation
                    </>
                  )}
                </button>
                {tier2Job && !tier2Running && tier2Job.status === "complete" && (
                  <p className="mt-2 text-xs text-muted-foreground flex items-center gap-1">
                    <CheckCircle2 className="w-3.5 h-3.5 text-green-500" />
                    Last pass: {tier2Job.confirmed} confirmed · {tier2Job.rejected} rejected
                    {tier2Job.errors > 0 && ` · ${tier2Job.errors} errors`}
                  </p>
                )}
                <p className="mt-1.5 text-xs text-muted-foreground">
                  Falls back to deterministic check when external LLM is not configured.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* Tier-1 scan performance */}
        <section
          aria-labelledby="perf-heading"
          className="rounded-lg border border-border bg-card p-5"
        >
          <h2 id="perf-heading" className="font-semibold mb-4 flex items-center gap-2">
            <Activity className="w-4 h-4 text-muted-foreground" />
            Tier-1 scan performance
          </h2>
          <ScanPerformance scans={scans} loading={scansLoading} />
        </section>

        {/* Bottom two-column */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Classification breakdown */}
          <section aria-labelledby="breakdown-heading" className="rounded-lg border border-border bg-card p-5">
            <h2 id="breakdown-heading" className="font-semibold mb-4">
              Findings by type
            </h2>
            <ClassificationBreakdown
              data={aggregates?.by_classification ?? []}
              loading={aggLoading}
            />
          </section>

          {/* Throughput chart */}
          <section aria-labelledby="throughput-heading" className="rounded-lg border border-border bg-card p-5">
            <h2 id="throughput-heading" className="font-semibold mb-4">
              Scan throughput
            </h2>
            <ThroughputChart scans={scans} loading={scansLoading} />
          </section>
        </div>
      </main>
    </div>
  );
}
