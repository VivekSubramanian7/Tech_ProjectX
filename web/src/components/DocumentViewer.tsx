import { useEffect, useState, type ReactNode } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { FileText, X, AlertCircle, Loader2, Presentation, Image as ImageIcon } from "lucide-react";
import { api, type OwnerFinding, type FileContentPreview } from "@/lib/api";
import { cn } from "@/lib/utils";

interface Props {
  finding: OwnerFinding | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

type TextSpan = [number, number];

function getTextSpan(location: Record<string, unknown>): TextSpan | null {
  const span = location.span;
  if (
    location.modality !== "text" ||
    !Array.isArray(span) ||
    span.length !== 2 ||
    typeof span[0] !== "number" ||
    typeof span[1] !== "number"
  ) {
    return null;
  }
  const [start, end] = span as TextSpan;
  if (start < 0 || end <= start) {
    return null;
  }
  return [start, end];
}

function highlightText(content: string, location: Record<string, unknown>): ReactNode {
  const span = getTextSpan(location);
  if (!span || span[1] > content.length) {
    return content;
  }
  const [start, end] = span;
  if (start >= end) {
    return content;
  }
  return (
    <>
      {content.slice(0, start)}
      <mark className="bg-primary/25 text-foreground rounded px-0.5">{content.slice(start, end)}</mark>
      {content.slice(end)}
    </>
  );
}

function highlightRange(text: string, globalStart: number, globalEnd: number, span: TextSpan | null): ReactNode {
  if (!span) {
    return text;
  }
  const [s, e] = span;
  if (e <= globalStart || s >= globalEnd) {
    return text;
  }
  const localStart = Math.max(0, s - globalStart);
  const localEnd = Math.min(text.length, e - globalStart);
  if (localStart >= localEnd) {
    return text;
  }
  return (
    <>
      {text.slice(0, localStart)}
      <mark className="bg-primary/25 text-foreground rounded px-0.5">{text.slice(localStart, localEnd)}</mark>
      {text.slice(localEnd)}
    </>
  );
}

function isImagePreview(preview: FileContentPreview): boolean {
  return preview.media_type?.startsWith("image/") ?? false;
}

type BBox = [number, number, number, number];

function getImageBBox(location: Record<string, unknown>): BBox | null {
  const bbox = location.bbox;
  if (
    location.modality === "image" &&
    Array.isArray(bbox) &&
    bbox.length === 4 &&
    bbox.every((n) => typeof n === "number")
  ) {
    return bbox as BBox;
  }
  return null;
}

/** Image preview with the finding region highlighted (bbox is normalized 0–1). */
function ImagePreviewBody({ preview, finding }: { preview: FileContentPreview; finding: OwnerFinding }) {
  const bbox = getImageBBox(finding.location);
  return (
    <div className="relative inline-block max-w-full">
      <img
        src={preview.content ?? ""}
        alt={finding.file_path.split(/[/\\]/).pop() ?? "document image"}
        className="max-w-full max-h-[24rem] rounded-md border border-border object-contain"
      />
      {bbox && (
        <div
          className="absolute border-2 border-primary bg-primary/15 rounded-sm pointer-events-none"
          style={{
            left: `${bbox[0] * 100}%`,
            top: `${bbox[1] * 100}%`,
            width: `${bbox[2] * 100}%`,
            height: `${bbox[3] * 100}%`,
          }}
          aria-hidden
        />
      )}
    </div>
  );
}

function isDocxPreview(preview: FileContentPreview): boolean {
  return preview.media_type?.includes("wordprocessingml") ?? false;
}

function isPptxPreview(preview: FileContentPreview): boolean {
  return preview.media_type?.includes("presentationml") ?? false;
}

interface SlideSection {
  number: number;
  text: string;
  start: number;
  end: number;
}

function parsePptxSections(content: string): SlideSection[] {
  const sections: SlideSection[] = [];
  let pos = 0;

  while (pos < content.length) {
    if (pos > 0 && content.startsWith("\n\n", pos)) {
      pos += 2;
    }
    const rest = content.slice(pos);
    const match = rest.match(/^--- Slide (\d+) ---\n/);
    if (!match) {
      break;
    }
    const number = Number(match[1]);
    const textStart = pos + match[0].length;
    const nextHeader = content.indexOf("\n\n--- Slide ", textStart);
    const textEnd = nextHeader === -1 ? content.length : nextHeader;
    sections.push({
      number,
      text: content.slice(textStart, textEnd),
      start: textStart,
      end: textEnd,
    });
    pos = textEnd;
  }

  return sections;
}

function DocumentPreviewBody({
  preview,
  finding,
}: {
  preview: FileContentPreview;
  finding: OwnerFinding;
}) {
  const content = preview.content ?? "";
  const span = getTextSpan(finding.location);

  if (isImagePreview(preview)) {
    return <ImagePreviewBody preview={preview} finding={finding} />;
  }

  if (isPptxPreview(preview)) {
    const slides = parsePptxSections(content);
    if (slides.length === 0) {
      return (
        <p className="text-sm text-muted-foreground italic">
          No slide text could be extracted from this presentation.
        </p>
      );
    }
    return (
      <div className="space-y-3">
        {slides.map((slide) => (
          <section
            key={slide.number}
            className="rounded-md border border-border bg-muted/30 overflow-hidden"
          >
            <header className="flex items-center gap-2 border-b border-border bg-muted/50 px-3 py-2">
              <Presentation className="w-3.5 h-3.5 text-primary shrink-0" />
              <span className="text-xs font-medium text-muted-foreground">Slide {slide.number}</span>
            </header>
            <div className="px-3 py-2 text-sm leading-relaxed whitespace-pre-wrap break-words">
              {highlightRange(slide.text, slide.start, slide.end, span)}
            </div>
          </section>
        ))}
      </div>
    );
  }

  const className = cn(
    "text-sm whitespace-pre-wrap break-words leading-relaxed",
    isDocxPreview(preview) ? "font-sans" : "font-mono text-xs"
  );

  return <pre className={className}>{highlightText(content, finding.location)}</pre>;
}

export function DocumentViewer({ finding, open, onOpenChange }: Props) {
  const [preview, setPreview] = useState<FileContentPreview | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || !finding) {
      setPreview(null);
      setError(null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    api.owner
      .fileContent(finding.file_id)
      .then((res) => {
        if (!cancelled) {
          setPreview(res.data);
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "Could not load document");
          setPreview(null);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [open, finding?.file_id]);

  if (!finding) {
    return null;
  }

  const fileName = finding.file_path.split(/[/\\]/).pop() ?? finding.file_path;
  const lowerName = fileName.toLowerCase();
  const isPresentation = lowerName.endsWith(".pptx");
  const isImage = /\.(jpe?g|png|gif|webp)$/.test(lowerName);

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/50 data-[state=open]:animate-in data-[state=closed]:animate-out" />
        <Dialog.Content
          className={cn(
            "fixed z-50 left-1/2 top-1/2 w-[min(100vw-2rem,42rem)] max-h-[min(85vh,32rem)]",
            "-translate-x-1/2 -translate-y-1/2 rounded-lg border border-border bg-card shadow-lg",
            "flex flex-col focus:outline-none"
          )}
          aria-describedby={undefined}
        >
          <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-3">
            <Dialog.Title className="text-sm font-semibold flex items-center gap-2 min-w-0">
              {isPresentation ? (
                <Presentation className="w-4 h-4 shrink-0 text-primary" />
              ) : isImage ? (
                <ImageIcon className="w-4 h-4 shrink-0 text-primary" />
              ) : (
                <FileText className="w-4 h-4 shrink-0 text-primary" />
              )}
              <span className="truncate" title={finding.file_path}>
                {fileName}
              </span>
            </Dialog.Title>
            <Dialog.Close
              className="rounded-md p-1 text-muted-foreground hover:text-foreground hover:bg-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring"
              aria-label="Close document preview"
            >
              <X className="w-4 h-4" />
            </Dialog.Close>
          </div>

          <div className="flex-1 overflow-auto p-4">
            {loading && (
              <div className="flex items-center justify-center gap-2 py-12 text-sm text-muted-foreground">
                <Loader2 className="w-4 h-4 animate-spin" /> Loading document…
              </div>
            )}

            {error && !loading && (
              <div className="flex items-start gap-2 text-sm text-destructive">
                <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                <p>{error}</p>
              </div>
            )}

            {!loading && !error && preview?.renderable && preview.content !== null && (
              <DocumentPreviewBody preview={preview} finding={finding} />
            )}

            {!loading && !error && preview?.renderable && preview.content === "" && (
              <p className="text-sm text-muted-foreground italic">This document has no extractable text.</p>
            )}

            {!loading && !error && preview && !preview.renderable && (
              <LocationFallback finding={finding} reason={preview.unsupported_reason} />
            )}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function LocationFallback({
  finding,
  reason,
}: {
  finding: OwnerFinding;
  reason: string | null | undefined;
}) {
  const loc = finding.location;
  const hint =
    reason === "unsupported_type"
      ? "This file type cannot be previewed in the browser."
      : reason === "extract_failed"
        ? "This Office document could not be read for preview."
        : reason === "binary_file"
          ? "This file could not be read as text."
          : "The original file is not available on disk for preview.";

  return (
    <div className="space-y-3 text-sm">
      <p className="text-muted-foreground">{hint}</p>
      <dl className="rounded-md border border-border bg-muted/40 px-3 py-2 space-y-2">
        <div>
          <dt className="text-xs text-muted-foreground">File path</dt>
          <dd className="font-mono text-xs break-all">{finding.file_path}</dd>
        </div>
        {loc.modality === "text" && Array.isArray(loc.span) && (
          <div>
            <dt className="text-xs text-muted-foreground">Character range</dt>
            <dd className="font-mono text-xs">
              {(loc.span as number[])[0]}–{(loc.span as number[])[1]}
            </dd>
          </div>
        )}
        {loc.modality === "image" && Array.isArray(loc.bbox) && (
          <div>
            <dt className="text-xs text-muted-foreground">Region (bbox)</dt>
            <dd className="font-mono text-xs">{(loc.bbox as number[]).join(", ")}</dd>
          </div>
        )}
        <div>
          <dt className="text-xs text-muted-foreground">Masked snippet</dt>
          <dd className="font-mono text-xs">{finding.masked_snippet}</dd>
        </div>
      </dl>
    </div>
  );
}
