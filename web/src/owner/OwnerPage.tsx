import { useState, useEffect, useCallback, useMemo } from "react";

import { AlertTriangle, LogOut, RefreshCw, User, Bell, LayoutList, Square } from "lucide-react";

import { toast } from "sonner";

import { api, DEMO_OWNERS, type OwnerFinding } from "@/lib/api";

import {

  ALL_FILTER,

  buildCategoryOptions,

  buildFileTypeOptions,

  categoryFilterKey,

  fileTypeFilterKey,

  filterFindings,

  filtersActive,

  loadStoredFilter,

} from "@/lib/ownerFilters";

import { countUniqueFiles, groupFindingsByFile, type FileGroup } from "@/lib/ownerGrouping";

import { useRole } from "@/lib/rbac";

import { FileGroupCard } from "@/components/FileGroupCard";

import { FileGroupListRow } from "@/components/FileGroupListRow";

import { DocumentViewer } from "@/components/DocumentViewer";

import { OwnerQueueFilters } from "@/components/OwnerQueueFilters";

import { QueueProgress } from "@/components/QueueProgress";

import { cn } from "@/lib/utils";



type PendingAction = "keep" | "escalate" | null;

type QueueView = "focus" | "list";



const VIEW_KEY = "gdpr_owner_queue_view";



function loadViewPreference(): QueueView {

  const stored = localStorage.getItem(VIEW_KEY);

  return stored === "list" ? "list" : "focus";

}



export default function OwnerPage() {

  const { setRole, ownerUserId, setOwnerUserId } = useRole();

  const [findings, setFindings] = useState<OwnerFinding[]>([]);

  const [sessionTotalFiles, setSessionTotalFiles] = useState(0);

  const [loading, setLoading] = useState(true);

  const [error, setError] = useState<string | null>(null);

  const [queueView, setQueueView] = useState<QueueView>(loadViewPreference);

  const [pendingAction, setPendingAction] = useState<PendingAction>(null);

  const [acting, setActing] = useState(false);

  const [activeFileId, setActiveFileId] = useState<string | null>(null);

  const [previewFinding, setPreviewFinding] = useState<OwnerFinding | null>(null);

  const [previewOpen, setPreviewOpen] = useState(false);

  const [categoryFilter, setCategoryFilter] = useState(ALL_FILTER);

  const [fileTypeFilter, setFileTypeFilter] = useState(ALL_FILTER);



  useEffect(() => {

    setCategoryFilter(loadStoredFilter(categoryFilterKey(ownerUserId)));

    setFileTypeFilter(loadStoredFilter(fileTypeFilterKey(ownerUserId)));

    setPendingAction(null);

    setActiveFileId(null);

  }, [ownerUserId]);



  const categoryOptions = useMemo(() => buildCategoryOptions(findings), [findings]);

  const fileTypeOptions = useMemo(() => buildFileTypeOptions(findings), [findings]);



  const visibleFindings = useMemo(

    () => filterFindings(findings, categoryFilter, fileTypeFilter),

    [findings, categoryFilter, fileTypeFilter]

  );



  const allGroups = useMemo(() => groupFindingsByFile(findings), [findings]);

  const visibleGroups = useMemo(

    () => groupFindingsByFile(visibleFindings),

    [visibleFindings]

  );



  const resolvedFiles = Math.max(sessionTotalFiles - allGroups.length, 0);

  const remainingFiles = allGroups.length;

  const filterIsActive = filtersActive(categoryFilter, fileTypeFilter);



  useEffect(() => {

    if (!categoryFilter) return;

    if (!categoryOptions.some((c) => c.code === categoryFilter)) {

      setCategoryFilter(ALL_FILTER);

      localStorage.removeItem(categoryFilterKey(ownerUserId));

    }

  }, [categoryOptions, categoryFilter, ownerUserId]);



  useEffect(() => {

    if (!fileTypeFilter) return;

    if (!fileTypeOptions.some((t) => t.key === fileTypeFilter)) {

      setFileTypeFilter(ALL_FILTER);

      localStorage.removeItem(fileTypeFilterKey(ownerUserId));

    }

  }, [fileTypeOptions, fileTypeFilter, ownerUserId]);



  useEffect(() => {

    if (activeFileId === null) return;

    if (!visibleGroups.some((g) => g.file_id === activeFileId)) {

      setPendingAction(null);

      setActiveFileId(null);

    }

  }, [visibleGroups, activeFileId]);



  const fetchQueue = useCallback(() => {

    setLoading(true);

    api.owner

      .findings()

      .then((res) => {

        setFindings(res.data);

        setSessionTotalFiles(countUniqueFiles(res.data));

        setError(null);

      })

      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load queue"))

      .finally(() => setLoading(false));

  }, []);



  useEffect(() => {

    fetchQueue();

  }, [fetchQueue, ownerUserId]);



  function setView(mode: QueueView) {

    setQueueView(mode);

    localStorage.setItem(VIEW_KEY, mode);

    setPendingAction(null);

    setActiveFileId(null);

  }



  function setCategory(code: string) {

    setCategoryFilter(code);

    const key = categoryFilterKey(ownerUserId);

    if (code) {

      localStorage.setItem(key, code);

    } else {

      localStorage.removeItem(key);

    }

  }



  function setFileType(key: string) {

    setFileTypeFilter(key);

    const storageKey = fileTypeFilterKey(ownerUserId);

    if (key) {

      localStorage.setItem(storageKey, key);

    } else {

      localStorage.removeItem(storageKey);

    }

  }



  function clearFilters() {

    setCategory(ALL_FILTER);

    setFileType(ALL_FILTER);

  }



  const focusGroup = visibleGroups[0] ?? null;

  const activeGroup =

    visibleGroups.find((g) => g.file_id === activeFileId) ??

    (queueView === "focus" ? focusGroup : null);



  function removeFindings(ids: number[]) {

    const idSet = new Set(ids);

    setFindings((items) => items.filter((f) => !idSet.has(f.id)));

    setPendingAction(null);

    setActiveFileId(null);

  }



  async function runBatchAction(

    group: FileGroup,

    action: (id: number) => Promise<unknown>,

    onSuccess?: () => void

  ) {

    setActing(true);

    try {

      for (const id of group.findingIds) {

        await action(id);

      }

      onSuccess?.();

      removeFindings(group.findingIds);

    } catch (e) {

      toast.error(e instanceof Error ? e.message : "Action failed");

      fetchQueue();

    } finally {

      setActing(false);

    }

  }



  function handleDelete(group: FileGroup) {

    const ids = [...group.findingIds];

    removeFindings(ids);



    Promise.all(ids.map((id) => api.owner.delete(id)))

      .then(() => {

        toast("Scheduled for deletion in 14 days", {

          description: `${ids.length} detection${ids.length === 1 ? "" : "s"} in this file. You can undo if this was a mistake.`,

          action: {

            label: "Undo",

            onClick: () => {

              Promise.all(ids.map((id) => api.owner.restore(id))).then(() => {

                toast.success("Deletion cancelled");

                fetchQueue();

              });

            },

          },

        });

      })

      .catch((e) => {

        toast.error(e instanceof Error ? e.message : "Delete failed");

        fetchQueue();

      });

  }



  function handleFalsePositive(group: FileGroup) {

    runBatchAction(

      group,

      (id) => api.owner.falsePositive(id),

      () => toast.success("Thanks — this sharpens detection")

    );

  }



  function handleReasonSubmit(reason: string) {

    if (!activeGroup || !pendingAction) return;

    if (pendingAction === "keep") {

      runBatchAction(

        activeGroup,

        (id) => api.owner.keep(id, reason),

        () => toast.success("Marked as kept — you can change this later")

      );

    } else {

      runBatchAction(

        activeGroup,

        (id) => api.owner.escalate(id, reason),

        () => toast.success("Escalated to your line manager")

      );

    }

  }



  function openDocument(group: FileGroup) {

    setPreviewFinding(group.findings[0] ?? null);

    setPreviewOpen(true);

  }



  function startPending(group: FileGroup, action: PendingAction) {

    setPendingAction(action);

    setActiveFileId(group.file_id);

  }



  const allClear = !loading && findings.length === 0;

  const filteredEmpty =

    !loading && findings.length > 0 && visibleFindings.length === 0 && filterIsActive;

  const showFocusCard = !loading && queueView === "focus" && focusGroup;

  const showList = !loading && queueView === "list" && visibleGroups.length > 0;



  return (

    <div className="min-h-screen bg-background">

      <header className="sticky top-0 z-10 border-b border-border bg-card/80 backdrop-blur-sm">

        <div className="max-w-3xl mx-auto px-4 h-14 flex items-center justify-between">

          <div className="flex items-center gap-2">

            <User className="w-5 h-5 text-primary" />

            <span className="font-semibold text-sm">GDPR Discovery</span>

            <span className="text-xs text-muted-foreground bg-muted rounded px-1.5 py-0.5 ml-1">

              Owner

            </span>

          </div>

          <div className="flex items-center gap-3">

            <label className="flex items-center gap-1.5 text-xs text-muted-foreground">

              <span className="sr-only">Acting as</span>

              <select

                value={ownerUserId}

                onChange={(e) => setOwnerUserId(e.target.value)}

                className="rounded-md border border-border bg-background px-2 py-1 text-xs text-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring"

                aria-label="Switch demo owner"

              >

                {DEMO_OWNERS.map((o) => (

                  <option key={o.id} value={o.id}>

                    {o.label} ({o.id})

                  </option>

                ))}

              </select>

            </label>

            <button

              onClick={fetchQueue}

              className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"

              aria-label="Refresh queue"

            >

              <RefreshCw className="w-3.5 h-3.5" />

            </button>

            <button

              onClick={() => setRole(null)}

              className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"

            >

              <LogOut className="w-3.5 h-3.5" /> Switch role

            </button>

          </div>

        </div>

      </header>



      <main className="max-w-3xl mx-auto px-4 py-8 space-y-6">

        <section aria-labelledby="queue-heading" className="space-y-2">

          <div className="flex flex-wrap items-center justify-between gap-3">

            <h1 id="queue-heading" className="text-lg font-semibold">

              My findings

            </h1>

            <div className="flex items-center gap-2">

              <div

                className="inline-flex rounded-md border border-border p-0.5 bg-muted/50"

                role="group"

                aria-label="Queue view"

              >

                <button

                  type="button"

                  onClick={() => setView("focus")}

                  className={cn(

                    "inline-flex items-center gap-1 rounded px-2 py-1 text-xs font-medium transition-colors",

                    queueView === "focus"

                      ? "bg-card text-foreground shadow-sm"

                      : "text-muted-foreground hover:text-foreground"

                  )}

                  aria-pressed={queueView === "focus"}

                >

                  <Square className="w-3.5 h-3.5" /> Focus

                </button>

                <button

                  type="button"

                  onClick={() => setView("list")}

                  className={cn(

                    "inline-flex items-center gap-1 rounded px-2 py-1 text-xs font-medium transition-colors",

                    queueView === "list"

                      ? "bg-card text-foreground shadow-sm"

                      : "text-muted-foreground hover:text-foreground"

                  )}

                  aria-pressed={queueView === "list"}

                >

                  <LayoutList className="w-3.5 h-3.5" /> List

                </button>

              </div>

              <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">

                <Bell className="w-3.5 h-3.5" /> In-app notifications enabled

              </span>

            </div>

          </div>

          <p className="text-sm text-muted-foreground">

            {queueView === "focus"

              ? "Work through your files one at a time. Each card may contain several related detections."

              : "Dense list view — act on any file. Same actions as Focus mode."}

          </p>

        </section>



        {error && (

          <div className="flex items-center gap-2 text-sm text-destructive bg-destructive/5 rounded-md px-3 py-2">

            <AlertTriangle className="w-4 h-4" /> {error}

            <span className="text-xs text-muted-foreground ml-1">

              (start the backend: <code>uvicorn app.main:app --reload</code>)

            </span>

          </div>

        )}



        <QueueProgress

          resolved={resolvedFiles}

          total={sessionTotalFiles}

          remaining={remainingFiles}

          allClear={allClear}

          filteredFileCount={visibleGroups.length}

          filterActive={filterIsActive}

        />



        {!loading && findings.length > 0 && (

          <OwnerQueueFilters

            categories={categoryOptions}

            fileTypes={fileTypeOptions}

            categoryCode={categoryFilter}

            fileType={fileTypeFilter}

            onCategoryChange={setCategory}

            onFileTypeChange={setFileType}

            onClear={clearFilters}

            visibleCount={visibleFindings.length}

            totalCount={findings.length}

          />

        )}



        {filteredEmpty && (

          <p className="text-sm text-muted-foreground text-center py-8 rounded-lg border border-dashed border-border">

            No files match these filters.{" "}

            <button type="button" className="text-primary hover:underline" onClick={clearFilters}>

              Clear filters

            </button>{" "}

            to see your full queue.

          </p>

        )}



        {loading && (

          <div className="rounded-lg border border-border bg-card p-6 space-y-4">

            <div className="h-6 w-48 rounded bg-muted animate-pulse" />

            <div className="h-4 w-full rounded bg-muted animate-pulse" />

            <div className="h-16 w-full rounded bg-muted animate-pulse" />

            <div className="h-10 w-64 rounded bg-muted animate-pulse" />

          </div>

        )}



        {showFocusCard && (

          <FileGroupCard

            group={focusGroup}

            pendingAction={activeFileId === focusGroup.file_id ? pendingAction : null}

            acting={acting}

            onKeep={() => startPending(focusGroup, "keep")}

            onDelete={() => handleDelete(focusGroup)}

            onEscalate={() => startPending(focusGroup, "escalate")}

            onFalsePositive={() => handleFalsePositive(focusGroup)}

            onReasonSubmit={handleReasonSubmit}

            onReasonCancel={() => {

              setPendingAction(null);

              setActiveFileId(null);

            }}

            onOpenDocument={() => openDocument(focusGroup)}

          />

        )}



        {showList && (

          <ul className="space-y-3" aria-label="Files list">

            {visibleGroups.map((group) => (

              <li key={group.file_id}>

                <FileGroupListRow

                  group={group}

                  pendingAction={activeFileId === group.file_id ? pendingAction : null}

                  acting={acting}

                  onKeep={() => startPending(group, "keep")}

                  onDelete={() => handleDelete(group)}

                  onEscalate={() => startPending(group, "escalate")}

                  onFalsePositive={() => handleFalsePositive(group)}

                  onReasonSubmit={handleReasonSubmit}

                  onReasonCancel={() => {

                    setPendingAction(null);

                    setActiveFileId(null);

                  }}

                  onOpenDocument={() => openDocument(group)}

                />

              </li>

            ))}

          </ul>

        )}



        {queueView === "focus" && visibleGroups.length > 1 && (

          <p className="text-xs text-muted-foreground text-center">

            {visibleGroups.length - 1} more file{visibleGroups.length - 1 === 1 ? "" : "s"}{" "}

            {filterIsActive ? "in this filter" : "after this one"}

            {" · "}

            <button

              type="button"

              className="text-primary hover:underline"

              onClick={() => setView("list")}

            >

              Switch to list view

            </button>

          </p>

        )}



        {activeFileId !== null && pendingAction && (

          <p className="sr-only" aria-live="polite">

            Reason picker open for file {activeFileId}

          </p>

        )}

      </main>



      <DocumentViewer

        finding={previewFinding}

        open={previewOpen}

        onOpenChange={(open) => {

          setPreviewOpen(open);

          if (!open) {

            setPreviewFinding(null);

          }

        }}

      />

    </div>

  );

}


