import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

interface Props {
  label: string;
  value: string | number;
  sub?: string;
  icon?: ReactNode;
  loading?: boolean;
}

export function KpiTile({ label, value, sub, icon, loading = false }: Props) {
  return (
    <div className="rounded-lg border border-border bg-card p-5 flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">{label}</span>
        {icon && <span className="text-muted-foreground">{icon}</span>}
      </div>
      {loading ? (
        <div className="h-8 w-24 rounded bg-muted animate-pulse" />
      ) : (
        <span className="text-3xl font-semibold tabular-nums">{value}</span>
      )}
      {sub && <span className="text-xs text-muted-foreground">{sub}</span>}
    </div>
  );
}
