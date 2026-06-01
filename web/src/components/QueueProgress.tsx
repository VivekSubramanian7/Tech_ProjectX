interface Props {
  resolved: number;
  total: number;
  remaining: number;
  allClear?: boolean;
  filteredFileCount?: number;
  filterActive?: boolean;
}

export function QueueProgress({
  resolved,
  total,
  remaining,
  allClear,
  filteredFileCount,
  filterActive,
}: Props) {
  const pct = total > 0 ? Math.round((resolved / total) * 100) : 100;
  const showFilterNote =
    filterActive && filteredFileCount !== undefined && filteredFileCount !== remaining;

  return (
    <div
      className="rounded-lg border border-border bg-card p-5"
      aria-live="polite"
      aria-label={allClear ? "All files resolved" : `${resolved} of ${total} files resolved`}
    >
      {allClear || total === 0 ? (
        <div className="text-center py-2">
          <p className="text-lg font-semibold">All clear</p>
          <p className="text-sm text-muted-foreground mt-1">Nothing needs your attention right now.</p>
        </div>
      ) : (
        <>
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium">
              {resolved} of {total} files resolved
            </span>
            <span className="text-xs text-muted-foreground">
              {remaining} file{remaining === 1 ? "" : "s"} remaining
            </span>
          </div>
          {showFilterNote && (
            <p className="text-xs text-muted-foreground mb-2">
              {filteredFileCount} file{filteredFileCount === 1 ? "" : "s"} in this filter · {remaining}{" "}
              remaining overall
            </p>
          )}
          <div className="h-2 rounded-full bg-muted overflow-hidden">
            <div
              className="h-full rounded-full bg-primary transition-all"
              style={{ width: `${pct}%` }}
            />
          </div>
        </>
      )}
    </div>
  );
}
