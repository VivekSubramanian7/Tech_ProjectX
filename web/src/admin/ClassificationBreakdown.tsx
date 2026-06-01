import type { ClassificationBucket } from "@/lib/api";
import { RISK_EDGE } from "@/lib/risk";
import { cn } from "@/lib/utils";

interface Props {
  data: ClassificationBucket[];
  loading?: boolean;
}

export default function ClassificationBreakdown({ data, loading }: Props) {
  if (loading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="h-8 rounded bg-muted animate-pulse" />
        ))}
      </div>
    );
  }

  if (!data.length) {
    return (
      <p className="text-sm text-muted-foreground py-6 text-center">
        No findings yet — start a scan to populate this view.
      </p>
    );
  }

  const max = Math.max(...data.map((d) => d.count), 1);

  return (
    <div className="space-y-2" aria-label="Findings by classification">
      {data.map((row) => (
        <div key={row.code} className="flex items-center gap-3">
          <div
            className={cn("w-1 h-6 rounded-full flex-shrink-0", RISK_EDGE[row.risk_weight] ?? "bg-muted")}
            aria-hidden
          />
          <div className="flex-1 min-w-0">
            <div className="flex justify-between mb-0.5">
              <span className="text-sm truncate" title={row.display_label}>
                {row.display_label}
              </span>
              <span className="text-sm font-medium tabular-nums ml-2">{row.count}</span>
            </div>
            <div className="h-1.5 rounded-full bg-muted overflow-hidden">
              <div
                className="h-full rounded-full bg-primary/70 transition-all"
                style={{ width: `${(row.count / max) * 100}%` }}
              />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
