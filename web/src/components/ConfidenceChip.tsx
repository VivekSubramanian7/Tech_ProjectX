import { cn } from "@/lib/utils";
import { HelpCircle, CheckCircle2 } from "lucide-react";

interface Props {
  label: "Likely" | "Not sure";
  className?: string;
}

export function ConfidenceChip({ label, className }: Props) {
  const Icon = label === "Likely" ? CheckCircle2 : HelpCircle;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border border-border bg-muted/60 px-2 py-0.5 text-xs font-medium text-muted-foreground",
        className
      )}
    >
      <Icon className="w-3 h-3" aria-hidden />
      {label}
    </span>
  );
}
