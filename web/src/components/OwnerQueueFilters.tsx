import { Filter, X } from "lucide-react";
import type { CategoryOption, FileTypeOption } from "@/lib/ownerFilters";
import { ALL_FILTER } from "@/lib/ownerFilters";
import { cn } from "@/lib/utils";

const selectClass = cn(
  "h-9 rounded-md border border-border bg-background px-2.5 text-sm",
  "focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring",
  "disabled:opacity-50 disabled:cursor-not-allowed"
);

interface Props {
  categories: CategoryOption[];
  fileTypes: FileTypeOption[];
  categoryCode: string;
  fileType: string;
  onCategoryChange: (code: string) => void;
  onFileTypeChange: (key: string) => void;
  onClear: () => void;
  visibleCount: number;
  totalCount: number;
  disabled?: boolean;
}

export function OwnerQueueFilters({
  categories,
  fileTypes,
  categoryCode,
  fileType,
  onCategoryChange,
  onFileTypeChange,
  onClear,
  visibleCount,
  totalCount,
  disabled,
}: Props) {
  const hasFilters = Boolean(categoryCode || fileType);

  return (
    <div
      className="rounded-lg border border-border bg-card px-4 py-3 space-y-3"
      aria-label="Filter findings"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="inline-flex items-center gap-1.5 text-sm font-medium">
          <Filter className="w-4 h-4 text-muted-foreground" />
          Filters
        </span>
        <span className="text-xs text-muted-foreground">
          Showing {visibleCount} of {totalCount} finding{totalCount === 1 ? "" : "s"}
        </span>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <label className="space-y-1">
          <span className="text-xs text-muted-foreground">Category</span>
          <select
            className={cn(selectClass, "w-full")}
            value={categoryCode}
            onChange={(e) => onCategoryChange(e.target.value)}
            disabled={disabled || categories.length === 0}
            aria-label="Filter by category"
          >
            <option value={ALL_FILTER}>All categories</option>
            {categories.map((c) => (
              <option key={c.code} value={c.code}>
                {c.label} ({c.count})
              </option>
            ))}
          </select>
        </label>

        <label className="space-y-1">
          <span className="text-xs text-muted-foreground">File type</span>
          <select
            className={cn(selectClass, "w-full")}
            value={fileType}
            onChange={(e) => onFileTypeChange(e.target.value)}
            disabled={disabled || fileTypes.length === 0}
            aria-label="Filter by file type"
          >
            <option value={ALL_FILTER}>All file types</option>
            {fileTypes.map((t) => (
              <option key={t.key} value={t.key}>
                {t.label} ({t.count})
              </option>
            ))}
          </select>
        </label>
      </div>

      {hasFilters && (
        <button
          type="button"
          onClick={onClear}
          disabled={disabled}
          className="inline-flex items-center gap-1 text-xs text-primary hover:underline disabled:opacity-50"
        >
          <X className="w-3 h-3" /> Clear filters
        </button>
      )}
    </div>
  );
}
