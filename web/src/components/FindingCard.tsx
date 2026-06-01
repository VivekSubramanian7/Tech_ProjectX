import { cn } from "@/lib/utils";
import type { OwnerFinding } from "@/lib/api";
import { RISK_EDGE } from "@/lib/risk";
import { ConfidenceChip } from "./ConfidenceChip";
import { MaskedSnippet } from "./MaskedSnippet";
import { ActionBar } from "./ActionBar";
import { ReasonPicker } from "./ReasonPicker";

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

export function FindingCard({
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
        <div className="flex-1 p-6 space-y-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h3 className="text-lg font-semibold">{finding.display_label}</h3>
              <p className="text-sm text-muted-foreground mt-1">{finding.consequence_hint}</p>
            </div>
            <ConfidenceChip label={finding.confidence_label} />
          </div>

          <MaskedSnippet
            snippet={finding.masked_snippet}
            filePath={finding.file_path}
            onOpenDocument={onOpenDocument}
          />

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
