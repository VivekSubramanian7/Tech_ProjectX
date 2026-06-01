import { useState, useEffect } from "react";
import { FolderOpen, Cloud, PlayCircle, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import { api, type ScanStatus, type Capabilities } from "@/lib/api";
import ScanProgress from "./ScanProgress";

type Source = "local" | "onedrive";

interface Props {
  onScanComplete?: (scanId: string) => void;
}

export default function ScanLauncher({ onScanComplete }: Props) {
  const [source, setSource] = useState<Source>("local");
  const [folderPath, setFolderPath] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [activeScanId, setActiveScanId] = useState<string | null>(null);
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let timer: ReturnType<typeof setInterval> | null = null;
    const load = () =>
      api
        .capabilities()
        .then((c) => {
          setCapabilities(c);
          if (c.models_ready && timer) clearInterval(timer);
        })
        .catch(() => null);
    load();
    timer = setInterval(load, 2000); // poll until image models finish warming
    return () => {
      if (timer) clearInterval(timer);
    };
  }, []);

  async function handleStart() {
    setError(null);
    if (source === "local" && !folderPath.trim()) {
      setError("Enter a folder path to scan.");
      return;
    }
    setSubmitting(true);
    try {
      const body =
        source === "local"
          ? { path: folderPath.trim(), mode: "full" as const, use_config: false }
          : { mode: "full" as const, use_config: true };
      const res = await api.scans.create(body);
      setActiveScanId(res.meta.scan_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start scan.");
    } finally {
      setSubmitting(false);
    }
  }

  function handleComplete(scan: ScanStatus) {
    onScanComplete?.(scan.scan_id);
  }

  if (activeScanId) {
    return (
      <ScanProgress
        scanId={activeScanId}
        onComplete={handleComplete}
        onReset={() => setActiveScanId(null)}
      />
    );
  }

  return (
    <div className="rounded-lg border border-border bg-card p-6 space-y-5">
      <h2 className="font-semibold text-foreground">Start a scan</h2>

      {/* Source picker */}
      <div className="flex gap-3">
        <SourceButton
          active={source === "local"}
          icon={<FolderOpen className="w-4 h-4" />}
          label="Local folder"
          onClick={() => setSource("local")}
        />
        <SourceButton
          active={source === "onedrive"}
          icon={<Cloud className="w-4 h-4" />}
          label="OneDrive"
          disabled={!capabilities?.graph_access}
          disabledReason="OneDrive requires Graph API access — not configured in this environment"
          onClick={() => capabilities?.graph_access && setSource("onedrive")}
        />
      </div>

      {/* Path input */}
      {source === "local" && (
        <div className="space-y-1.5">
          <label className="text-sm font-medium" htmlFor="folder-path">
            Folder path
          </label>
          <input
            id="folder-path"
            type="text"
            value={folderPath}
            onChange={(e) => setFolderPath(e.target.value)}
            placeholder="e.g. data/gdpr_synthetic_dataset_500/gdpr_synthetic_dataset_500/documents"
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring"
          />
          <p className="text-xs text-muted-foreground">Relative paths resolve from the project root.</p>
        </div>
      )}

      {error && (
        <p className="flex items-center gap-1.5 text-sm text-destructive" role="alert">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          {error}
        </p>
      )}

      <div className="flex items-center gap-3">
        <button
          onClick={handleStart}
          disabled={submitting}
          className={cn(
            "inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground",
            "hover:opacity-90 transition-opacity focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring",
            "disabled:opacity-50 disabled:cursor-not-allowed"
          )}
        >
          <PlayCircle className="w-4 h-4" />
          {submitting ? "Starting…" : "Start scan"}
        </button>
        {capabilities && (
          <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
            <span
              className={cn(
                "h-2 w-2 rounded-full",
                capabilities.models_ready ? "bg-green-500" : "bg-amber-400 animate-pulse"
              )}
              aria-hidden
            />
            {capabilities.models_ready ? "Image models ready" : "Warming image models…"}
          </span>
        )}
      </div>
    </div>
  );
}

function SourceButton({
  active,
  icon,
  label,
  disabled,
  disabledReason,
  onClick,
}: {
  active: boolean;
  icon: React.ReactNode;
  label: string;
  disabled?: boolean;
  disabledReason?: string;
  onClick: () => void;
}) {
  const btn = (
    <button
      onClick={onClick}
      disabled={disabled}
      aria-pressed={active}
      className={cn(
        "flex items-center gap-2 rounded-md border px-4 py-2 text-sm font-medium transition-colors",
        "focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring",
        active
          ? "border-primary bg-primary/10 text-primary"
          : "border-border bg-background text-foreground hover:bg-accent",
        disabled && "opacity-40 cursor-not-allowed"
      )}
    >
      {icon}
      {label}
    </button>
  );

  if (disabled && disabledReason) {
    return (
      <div className="relative group">
        {btn}
        <div
          role="tooltip"
          className="absolute bottom-full left-0 mb-1 hidden group-hover:block w-64 rounded-md border border-border bg-popover p-2 text-xs text-popover-foreground shadow-md z-10"
        >
          {disabledReason}
        </div>
      </div>
    );
  }
  return btn;
}
