import { cn } from "@/lib/utils";
import type { FileGroup } from "@/lib/ownerGrouping";
import { RISK_EDGE } from "@/lib/risk";
import { ActionBar } from "./ActionBar";
import { ReasonPicker } from "./ReasonPicker";
import { FileText } from "lucide-react";

type PendingAction = "keep" | "escalate" | null;

interface Props {
  group: FileGroup;
  pendingAction: PendingAction;
  acting?: boolean;
  onKeep: () => void;
  onDelete: () => void;
  onEscalate: () => void;
  onFalsePositive: () => void;
  onReasonSubmit: (reason: string) => void;
  onReasonCancel: () => void;
  onOpenDocument?: () => void;
}

export function FileGroupListRow({
  group,
  pendingAction,
  acting,
  onKeep,
  onDelete,
  onEscalate,
  onFalsePositive,
  onReasonSubmit,
  onReasonCancel,
  onOpenDocument,
}: Props) {
  const detectionCount = group.findings.length;

  return (
    <article
      className="rounded-lg border border-border bg-card overflow-hidden"
      aria-label={`File: ${group.file_name}, ${detectionCount} detections`}
    >
      <div className="flex">
        <div
          className={cn("w-1 flex-shrink-0", RISK_EDGE[group.highestRisk] ?? "bg-muted")}
          aria-hidden
        />
        <div className="flex-1 px-4 py-3 space-y-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="min-w-0">
              <h3 className="text-sm font-semibold">{group.file_name}</h3>
              <p className="text-xs text-muted-foreground truncate" title={group.file_path}>
                {group.file_path}
              </p>
              <p className="text-xs text-muted-foreground mt-0.5">
                {group.categories.length}{" "}
                {group.categories.length === 1 ? "category" : "categories"} · {detectionCount}{" "}
                {detectionCount === 1 ? "detection" : "detections"}
              </p>
            </div>
          </div>

          <div className="flex flex-wrap gap-1.5">
            {group.categories.map((cat) => (
              <span
                key={cat.code}
                className="inline-flex items-center gap-1 rounded-full border border-border bg-muted/40 px-2 py-0.5 text-[11px] font-medium"
              >
                <span
                  className={cn("w-1 h-1 rounded-full", RISK_EDGE[cat.risk_weight] ?? "bg-muted")}
                  aria-hidden
                />
                {cat.label} ×{cat.count}
              </span>
            ))}
          </div>

          {onOpenDocument && (
            <button
              type="button"
              onClick={onOpenDocument}
              className="inline-flex items-center gap-1 text-xs text-primary hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring rounded-sm"
            >
              <FileText className="w-3 h-3" /> Open document
            </button>
          )}

          {pendingAction ? (
            <ReasonPicker
              mode={pendingAction}
              onSubmit={onReasonSubmit}
              onCancel={onReasonCancel}
              loading={acting}
            />
          ) : (
            <ActionBar
              pendingAction={pendingAction}
              onKeep={onKeep}
              onDelete={onDelete}
              onEscalate={onEscalate}
              onFalsePositive={onFalsePositive}
              disabled={acting}
            />
          )}
        </div>
      </div>
    </article>
  );
}
