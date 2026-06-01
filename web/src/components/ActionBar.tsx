import { cn } from "@/lib/utils";
import { Trash2, HelpCircle, Ban, Archive } from "lucide-react";
import type { ReactNode } from "react";

type PendingAction = "keep" | "escalate" | null;

interface Props {
  pendingAction: PendingAction;
  onKeep: () => void;
  onDelete: () => void;
  onEscalate: () => void;
  onFalsePositive: () => void;
  disabled?: boolean;
}

export function ActionBar({
  pendingAction,
  onKeep,
  onDelete,
  onEscalate,
  onFalsePositive,
  disabled,
}: Props) {
  return (
    <div className="flex flex-wrap gap-2" role="group" aria-label="Finding actions">
      <ActionButton
        label="Keep"
        icon={<Archive className="w-4 h-4" />}
        onClick={onKeep}
        disabled={disabled || pendingAction !== null}
        variant="primary"
      />
      <ActionButton
        label="Delete"
        icon={<Trash2 className="w-4 h-4" />}
        onClick={onDelete}
        disabled={disabled || pendingAction !== null}
        variant="outline"
      />
      <ActionButton
        label="I'm not sure"
        icon={<HelpCircle className="w-4 h-4" />}
        onClick={onEscalate}
        disabled={disabled || pendingAction !== null}
        variant="ghost"
      />
      <ActionButton
        label="Not personal data"
        icon={<Ban className="w-4 h-4" />}
        onClick={onFalsePositive}
        disabled={disabled || pendingAction !== null}
        variant="ghost"
      />
    </div>
  );
}

function ActionButton({
  label,
  icon,
  onClick,
  disabled,
  variant,
}: {
  label: string;
  icon: ReactNode;
  onClick: () => void;
  disabled?: boolean;
  variant: "primary" | "outline" | "ghost";
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md px-3 py-2 text-sm font-medium transition-opacity",
        "focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring disabled:opacity-50",
        variant === "primary" && "bg-primary text-primary-foreground hover:opacity-90",
        variant === "outline" &&
          "border border-[hsl(28_80%_50%/0.45)] text-foreground hover:bg-accent",
        variant === "ghost" && "text-muted-foreground hover:text-foreground hover:bg-accent"
      )}
    >
      {icon}
      {label}
    </button>
  );
}
