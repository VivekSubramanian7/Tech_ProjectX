import { cn } from "@/lib/utils";

const KEEP_REASONS = [
  "Required for an active project",
  "Legal or compliance retention",
  "Shared with customer consent",
  "Other",
] as const;

const ESCALATE_REASONS = [
  "I don't have enough context",
  "Needs legal review",
  "This may not be my file",
] as const;

interface Props {
  mode: "keep" | "escalate";
  onSubmit: (reason: string) => void;
  onCancel: () => void;
  loading?: boolean;
}

export function ReasonPicker({ mode, onSubmit, onCancel, loading }: Props) {
  const options = mode === "keep" ? KEEP_REASONS : ESCALATE_REASONS;
  const title = mode === "keep" ? "Why do you still need this?" : "Why are you escalating?";

  return (
    <form
      className="rounded-md border border-border bg-muted/30 p-4 space-y-3"
      onSubmit={(e) => {
        e.preventDefault();
        const fd = new FormData(e.currentTarget);
        const selected = String(fd.get("reason") ?? "");
        const detail = String(fd.get("detail") ?? "").trim();
        const reason = detail ? `${selected}: ${detail}` : selected;
        if (selected) onSubmit(reason);
      }}
    >
      <p className="text-sm font-medium">{title}</p>
      <fieldset className="space-y-2">
        <legend className="sr-only">{title}</legend>
        {options.map((opt) => (
          <label key={opt} className="flex items-center gap-2 text-sm cursor-pointer">
            <input type="radio" name="reason" value={opt} required className="accent-primary" />
            {opt}
          </label>
        ))}
      </fieldset>
      <label className="block text-xs text-muted-foreground">
        Optional detail
        <input
          name="detail"
          type="text"
          className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
          placeholder="Add a short note if helpful"
        />
      </label>
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={loading}
          className={cn(
            "rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground",
            "hover:opacity-90 disabled:opacity-50"
          )}
        >
          {loading ? "Saving…" : "Confirm"}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="rounded-md border border-border px-3 py-1.5 text-sm hover:bg-accent"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
