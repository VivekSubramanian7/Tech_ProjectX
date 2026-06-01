import type { ScanStatus } from "@/lib/api";
import { formatBytes, formatDuration, formatThroughput } from "@/lib/utils";
import { Gauge, Clock, HardDrive, FileStack } from "lucide-react";

interface Props {
  scans: ScanStatus[];
  loading?: boolean;
}

/** Tier-1 scan performance: file type, total size, and time of the latest scan. */
export default function ScanPerformance({ scans, loading }: Props) {
  if (loading) {
    return <div className="h-40 rounded bg-muted animate-pulse" />;
  }

  const latest = scans.find((s) => s.status === "complete" && s.duration_ms != null);

  if (!latest) {
    return (
      <p className="text-sm text-muted-foreground py-6 text-center">
        No completed scans yet — run a scan to see Tier-1 throughput.
      </p>
    );
  }

  const totalBytes = latest.total_bytes ?? 0;
  const durMs = latest.duration_ms ?? 0;
  const filesPerSec = durMs > 0 ? (latest.files_scanned / (durMs / 1000)).toFixed(1) : "—";
  const byType = latest.type_breakdown ?? {};
  const types = Object.entries(byType).sort((a, b) => b[1].bytes - a[1].bytes);
  const maxBytes = Math.max(...types.map(([, v]) => v.bytes), 1);

  return (
    <div className="space-y-4">
      {/* Headline metrics */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Metric icon={<Clock className="w-4 h-4" />} label="Scan time" value={formatDuration(durMs)} />
        <Metric icon={<HardDrive className="w-4 h-4" />} label="Total size" value={formatBytes(totalBytes)} />
        <Metric icon={<Gauge className="w-4 h-4" />} label="Throughput" value={formatThroughput(totalBytes, durMs)} />
        <Metric icon={<FileStack className="w-4 h-4" />} label="Files / sec" value={String(filesPerSec)} />
      </div>

      {/* Per-file-type breakdown */}
      {types.length > 0 && (
        <div>
          <div className="flex items-center justify-between text-xs text-muted-foreground mb-2 px-1">
            <span>File type</span>
            <span>Files · Size</span>
          </div>
          <div className="space-y-1.5">
            {types.map(([ext, v]) => (
              <div key={ext} className="flex items-center gap-3">
                <span className="w-12 text-xs font-mono uppercase text-muted-foreground shrink-0">
                  .{ext}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="h-1.5 rounded-full bg-muted overflow-hidden">
                    <div
                      className="h-full rounded-full bg-primary/70"
                      style={{ width: `${(v.bytes / maxBytes) * 100}%` }}
                    />
                  </div>
                </div>
                <span className="text-xs tabular-nums text-muted-foreground shrink-0 w-28 text-right">
                  {v.files} · {formatBytes(v.bytes)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function Metric({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="rounded-md border border-border bg-background px-3 py-2">
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground mb-0.5">
        {icon}
        {label}
      </div>
      <div className="text-base font-semibold tabular-nums">{value}</div>
    </div>
  );
}
