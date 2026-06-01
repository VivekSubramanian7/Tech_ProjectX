import { useState } from "react";
import { ChevronDown, ChevronUp, FileText } from "lucide-react";
import { cn } from "@/lib/utils";
import type { FileGroup } from "@/lib/ownerGrouping";
import { RISK_EDGE } from "@/lib/risk";
import { ActionBar } from "./ActionBar";
import { ReasonPicker } from "./ReasonPicker";

type PendingAction = "keep" | "escalate" | null;

const SNIPPET_PREVIEW = 3;

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

export function FileGroupCard({
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
  const [expanded, setExpanded] = useState(false);
  const detectionCount = group.findings.length;
  const categoryCount = group.categories.length;
  const previewSnippets = expanded ? group.findings : group.findings.slice(0, SNIPPET_PREVIEW);
  const hiddenCount = detectionCount - SNIPPET_PREVIEW;

  return (
    <article
      className="rounded-lg border border-border bg-card overflow-hidden animate-in fade-in slide-in-from-bottom-2 duration-300"
      aria-label={`File: ${group.file_name}, ${detectionCount} detections`}
    >
      <div className="flex">
        <div
          className={cn("w-1 flex-shrink-0", RISK_EDGE[group.highestRisk] ?? "bg-muted")}
          aria-hidden
        />
        <div className="flex-1 p-6 space-y-4">
          <div className="space-y-1">
            <h3 className="text-lg font-semibold tracking-tight">{group.file_name}</h3>
            <p className="text-xs font-mono text-muted-foreground truncate" title={group.file_path}>
              {group.file_path}
            </p>
            <p className="text-sm text-muted-foreground">
              {categoryCount} {categoryCount === 1 ? "category" : "categories"} · {detectionCount}{" "}
              {detectionCount === 1 ? "detection" : "detections"}
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            {group.categories.map((cat) => (
              <span
                key={cat.code}
                className="inline-flex items-center gap-1.5 rounded-full border border-border bg-muted/40 px-2.5 py-1 text-xs font-medium"
              >
                <span
                  className={cn("w-1.5 h-1.5 rounded-full", RISK_EDGE[cat.risk_weight] ?? "bg-muted")}
                  aria-hidden
                />
                {cat.label} ×{cat.count}
              </span>
            ))}
          </div>

          <div className="space-y-2">
            {previewSnippets.map((f) => (
              <p
                key={f.id}
                className="font-mono text-sm tracking-wide text-muted-foreground border-l-2 border-border pl-3"
              >
                {f.masked_snippet}
              </p>
            ))}
            {hiddenCount > 0 && (
              <button
                type="button"
                onClick={() => setExpanded((v) => !v)}
                className="inline-flex items-center gap-1 text-xs text-primary hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring rounded-sm"
              >
                {expanded ? (
                  <>
                    <ChevronUp className="w-3 h-3" /> Show fewer
                  </>
                ) : (
                  <>
                    <ChevronDown className="w-3 h-3" /> +{hiddenCount} more
                  </>
                )}
              </button>
            )}
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
