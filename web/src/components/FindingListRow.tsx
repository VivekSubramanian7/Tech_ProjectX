import { cn } from "@/lib/utils";
import type { OwnerFinding } from "@/lib/api";
import { RISK_EDGE } from "@/lib/risk";
import { ConfidenceChip } from "./ConfidenceChip";
import { ActionBar } from "./ActionBar";
import { ReasonPicker } from "./ReasonPicker";
import { FileText } from "lucide-react";

type PendingAction = "keep" | "escalate" | null;

interface Props {
  finding: OwnerFinding;
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

export function FindingListRow({
  finding,
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
  return (
    <article
      className="rounded-lg border border-border bg-card overflow-hidden"
      aria-label={`Finding: ${finding.display_label}`}
    >
      <div className="flex">
        <div
          className={cn("w-1 flex-shrink-0", RISK_EDGE[finding.risk_weight] ?? "bg-muted")}
          aria-hidden
        />
        <div className="flex-1 px-4 py-3 space-y-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="min-w-0">
              <h3 className="text-sm font-semibold">{finding.display_label}</h3>
              <p className="text-xs text-muted-foreground truncate" title={finding.file_path}>
                {finding.file_path}
              </p>
            </div>
            <ConfidenceChip label={finding.confidence_label} />
          </div>

          <p className="font-mono text-xs tracking-wide text-muted-foreground">{finding.masked_snippet}</p>

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
