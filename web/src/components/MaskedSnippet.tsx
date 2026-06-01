import { FileText } from "lucide-react";

interface Props {
  snippet: string;
  filePath: string;
  onOpenDocument?: () => void;
}

export function MaskedSnippet({ snippet, filePath, onOpenDocument }: Props) {
  return (
    <div className="rounded-md border border-border bg-muted/40 px-3 py-2 space-y-1">
      <p className="font-mono text-sm tracking-wide" aria-label="Masked value">
        {snippet}
      </p>
      <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
        <span className="truncate" title={filePath}>
          {filePath}
        </span>
        {onOpenDocument && (
          <button
            type="button"
            onClick={onOpenDocument}
            className="inline-flex items-center gap-1 shrink-0 text-primary hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring rounded-sm"
          >
            <FileText className="w-3 h-3" /> Open document
          </button>
        )}
      </div>
    </div>
  );
}
