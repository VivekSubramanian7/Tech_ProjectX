import { useEffect, useRef, useState } from "react";
import { CheckCircle2, AlertCircle, RefreshCw, LayoutDashboard } from "lucide-react";
import { cn } from "@/lib/utils";
import { api, type ScanStatus } from "@/lib/api";

interface Props {
  scanId: string;
  onComplete: (scan: ScanStatus) => void;
  onReset: () => void;
}

const POLL_MS = 1500;

export default function ScanProgress({ scanId, onComplete, onReset }: Props) {
  const [scan, setScan] = useState<ScanStatus | null>(null);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    function poll() {
      api.scans
        .get(scanId)
        .then((res) => {
          setScan(res.data);
          setFetchError(null);
          if (res.data.status === "complete" || res.data.status === "error") {
            clearInterval(intervalRef.current!);
            onComplete(res.data);
          }
        })
        .catch((e) => setFetchError(e instanceof Error ? e.message : "Poll error"));
    }

    poll();
    intervalRef.current = setInterval(poll, POLL_MS);
    return () => clearInterval(intervalRef.current!);
  }, [scanId]);

  const pct =
    scan && scan.files_total > 0
      ? Math.round((scan.files_scanned / scan.files_total) * 100)
      : 0;

  const done = scan?.status === "complete";
  const errored = scan?.status === "error";
  const prepping =
    !!scan &&
    !done &&
    !errored &&
    scan.files_total > 0 &&
    scan.files_scanned === 0;
  const statusLabel =
    scan?.phase ?? (prepping ? "Preparing scan…" : null);

  return (
    <div className="rounded-lg border border-border bg-card p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold text-foreground">
          {done ? "Scan complete" : errored ? "Scan failed" : "Scanning…"}
        </h2>
        {(done || errored) && (
          <button
            onClick={onReset}
            className="text-xs text-muted-foreground hover:text-foreground inline-flex items-center gap-1 transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" /> New scan
          </button>
        )}
      </div>

      {fetchError && (
        <p className="flex items-center gap-1.5 text-sm text-destructive">
          <AlertCircle className="w-4 h-4" /> {fetchError}
        </p>
      )}

      {scan && (
        <>
          {/* Warmup / classify / model-load phase */}
          {!done && !errored && statusLabel && (
            <div
              className="flex items-center gap-2 text-sm text-primary bg-primary/5 rounded-md px-3 py-2"
              role="status"
              aria-live="polite"
            >
              <span className="h-3.5 w-3.5 rounded-full border-2 border-primary border-t-transparent animate-spin" />
              {statusLabel}
            </div>
          )}

          {/* Progress bar */}
          <div className="space-y-1.5">
            <div className="flex justify-between text-xs text-muted-foreground">
              <span aria-live="polite">
                {scan.files_scanned} of {scan.files_total} files
              </span>
              <span>{prepping ? "…" : `${pct}%`}</span>
            </div>
            <div
              className="h-2 rounded-full bg-muted overflow-hidden"
              role="progressbar"
              aria-valuenow={prepping ? undefined : pct}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-busy={prepping || undefined}
            >
              {prepping ? (
                <div className="h-full w-1/3 rounded-full bg-primary animate-pulse" />
              ) : (
                <div
                  className={cn(
                    "h-full rounded-full transition-all",
                    done ? "bg-green-500" : errored ? "bg-destructive" : "bg-primary"
                  )}
                  style={{ width: `${pct}%` }}
                />
              )}
            </div>
          </div>

          {/* Stats row */}
          <div className="grid grid-cols-3 gap-3 text-center">
            <Stat label="Files" value={scan.files_total} />
            <Stat label="Scanned" value={scan.files_scanned} />
            <Stat label="Findings" value={scan.findings_count} />
          </div>

          {!done && !errored && scan.current_file && (
            <p className="text-xs text-muted-foreground truncate" title={scan.current_file}>
              Processing: {scan.current_file.split(/[/\\]/).pop()}
            </p>
          )}

          {done && (
            <div className="flex items-center gap-2 text-sm text-green-700 bg-green-50 rounded-md px-3 py-2">
              <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
              Scan complete — {scan.findings_count} finding{scan.findings_count !== 1 ? "s" : ""} written to catalog
            </div>
          )}
        </>
      )}

      {done && (
        <button
          onClick={() => document.getElementById("kpi-section")?.scrollIntoView({ behavior: "smooth" })}
          className="inline-flex items-center gap-2 text-sm text-primary hover:underline"
        >
          <LayoutDashboard className="w-4 h-4" /> View dashboard
        </button>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md bg-muted px-3 py-2">
      <div className="text-lg font-semibold tabular-nums">{value}</div>
      <div className="text-xs text-muted-foreground">{label}</div>
    </div>
  );
}
